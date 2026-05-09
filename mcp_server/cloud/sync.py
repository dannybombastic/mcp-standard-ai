"""SyncManager: lógica de push/pull entre .ai/ local y la nube."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from mcp_server.cloud.client import CloudClient
from mcp_server.storage.paths import AIPaths
from mcp_server.storage.registry import RegistryManager

logger = logging.getLogger(__name__)


class SyncManager:
    """
    Orquesta la sincronización bidireccional entre el directorio .ai/ local
    y la plataforma cloud.

    Estrategia:
    - push: local → cloud (crea o actualiza assets en la nube)
    - pull: cloud → local (descarga assets de la nube al disco)
    - status: muestra diferencias entre local y cloud
    """

    def __init__(self, paths: AIPaths, registry: RegistryManager, client: CloudClient):
        self.paths = paths
        self.registry = registry
        self.client = client

    # ------------------------------------------------------------------
    # Push
    # ------------------------------------------------------------------

    async def push_all(self, project_slug: str | None = None, dry_run: bool = False) -> list[dict[str, Any]]:
        """
        Sube todos los assets locales a la nube.
        Retorna lista de resultados con {slug, type, action, status}.
        """
        self.registry.load()
        results: list[dict[str, Any]] = []

        if project_slug:
            await self.client.ensure_project(project_slug)

        asset_types = [
            ("skill", self.paths.skills),
            ("prompt", self.paths.prompts),
            ("spec", self.paths.specs),
        ]

        for asset_type, asset_dir in asset_types:
            if not asset_dir.exists():
                continue
            for md_file in sorted(asset_dir.glob("*.md")):
                result = await self._push_file(md_file, asset_type, project_slug, dry_run)
                results.append(result)

        if not dry_run:
            self.registry.save_if_dirty()

        return results

    async def push_asset(
        self,
        asset_type: str,
        slug: str,
        project_slug: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Sube un asset específico por tipo y slug."""
        self.registry.load()
        asset_dir = self.paths.asset_dir(asset_type)
        md_file = asset_dir / f"{slug}.md"
        if not md_file.exists():
            raise FileNotFoundError(f"No encontrado: {md_file}")
        result = await self._push_file(md_file, asset_type, project_slug, dry_run)
        if not dry_run:
            self.registry.save_if_dirty()
        return result

    async def _push_file(
        self,
        md_file: Path,
        asset_type: str,
        project_slug: str | None,
        dry_run: bool,
    ) -> dict[str, Any]:
        slug = md_file.stem
        content = md_file.read_text(encoding="utf-8")
        checksum = hashlib.sha256(content.encode()).hexdigest()

        # Obtener nombre desde front matter o usar slug
        name = _extract_name(content) or slug.replace("-", " ").title()
        existing = self.registry.get(asset_type, slug)
        cloud_id: str | None = str(existing.get("cloud_id")) if existing and existing.get("cloud_id") else None

        # Comprobar si ha cambiado (checksum local vs content_hash remoto guardado en registry si existía)
        if existing and existing.get("checksum") == checksum and cloud_id:
            return {"slug": slug, "type": asset_type, "action": "skip", "status": "no_changes"}

        if dry_run:
            action = "update" if cloud_id else "create"
            return {"slug": slug, "type": asset_type, "action": action, "status": "dry_run"}

        try:
            if not project_slug:
                raise ValueError("project_slug es requerido para push en el backend Django")

            asset_rel_path = str(md_file.relative_to(self.paths.ai_dir)).replace("\\", "/")

            result = await self.client.push_asset_content(
                local_path=md_file,
                asset_type=asset_type,
                project_slug=project_slug,
                asset_path=asset_rel_path,
                name=name,
                cloud_id=cloud_id,
            )
            action = "update" if cloud_id else "create"
            # Actualizar registry (Django retorna id UUID y content_hash puede venir vacío si el servidor no lo calcula)
            self.registry.upsert({
                "type": asset_type,
                "slug": slug,
                "name": name,
                "path": asset_rel_path,
                "tags": [],  # Django contract actual no guarda tags
                "cloud_id": result.get("id"),
                "cloud_slug": None,
                "synced_at": result.get("updated_at"),
                "checksum": checksum,
            })
            return {"slug": slug, "type": asset_type, "action": action, "status": "ok", "cloud_id": result.get("id")}
        except Exception as e:
            logger.error("Error pushing %s/%s: %s", asset_type, slug, e)
            return {"slug": slug, "type": asset_type, "action": "error", "status": str(e)}

    # ------------------------------------------------------------------
    # Pull
    # ------------------------------------------------------------------

    async def pull_all(self, project_slug: str | None = None, dry_run: bool = False) -> list[dict[str, Any]]:
        """
        Descarga todos los assets de la nube que no están en local
        o que tienen una versión más nueva.
        """
        self.registry.load()
        results: list[dict[str, Any]] = []

        for asset_type in ["skill", "prompt", "spec"]:
            cloud_assets = await self.client.list_assets(asset_type, project_slug=project_slug)
            for cloud_asset in cloud_assets:
                result = await self._pull_asset(cloud_asset, asset_type, dry_run)
                results.append(result)

        if not dry_run:
            self.registry.save_if_dirty()

        return results

    async def _pull_asset(
        self, cloud_asset: dict[str, Any], asset_type: str, dry_run: bool
    ) -> dict[str, Any]:
        cloud_id = str(cloud_asset.get("id"))
        remote_path = cloud_asset.get("path", "") or ""
        # Derivar slug desde el filename si el asset está en el directorio esperado (skills/foo.md => foo)
        slug = Path(remote_path).stem if remote_path else ""
        cloud_checksum = cloud_asset.get("content_hash", "") or ""

        existing = self.registry.get(asset_type, slug)
        if existing and existing.get("checksum") == cloud_checksum:
            return {"slug": slug, "type": asset_type, "action": "skip", "status": "no_changes"}

        if dry_run:
            action = "update" if existing else "create"
            return {"slug": slug, "type": asset_type, "action": action, "status": "dry_run"}

        try:
            asset_dir = self.paths.asset_dir(asset_type)
            target = asset_dir / f"{slug}.md"
            fetched = await self.client.pull_asset_content(cloud_id, target)
            content = target.read_text(encoding="utf-8")
            checksum = hashlib.sha256(content.encode()).hexdigest()
            name = fetched.get("name", slug)
            self.registry.upsert({
                "type": asset_type,
                "slug": slug,
                "name": name,
                "path": str(target.relative_to(self.paths.ai_dir)).replace("\\", "/"),
                "tags": [],
                "cloud_id": cloud_id,
                "cloud_slug": None,
                "synced_at": fetched.get("updated_at"),
                "checksum": checksum,
            })
            action = "update" if existing else "create"
            return {"slug": slug, "type": asset_type, "action": action, "status": "ok"}
        except Exception as e:
            logger.error("Error pulling %s/%s: %s", asset_type, slug, e)
            return {"slug": slug, "type": asset_type, "action": "error", "status": str(e)}

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def status(self, project_slug: str | None = None) -> dict[str, Any]:
        """Retorna el estado de sincronización local vs cloud."""
        self.registry.load()
        local_assets = self.registry.list_all()
        local_keys = {f"{a['type']}/{a['slug']}" for a in local_assets}

        cloud_keys: set[str] = set()
        for asset_type in ["skill", "prompt", "spec"]:
            try:
                cloud_list = await self.client.list_assets(asset_type, project_slug=project_slug)
                for ca in cloud_list:
                    remote_path = ca.get("path", "") or ""
                    slug = Path(remote_path).stem if remote_path else ""
                    cloud_keys.add(f"{asset_type}/{slug}")
            except Exception:
                pass

        only_local = local_keys - cloud_keys
        only_cloud = cloud_keys - local_keys
        synced = local_keys & cloud_keys

        return {
            "local_count": len(local_keys),
            "cloud_count": len(cloud_keys),
            "synced": sorted(synced),
            "only_local": sorted(only_local),
            "only_cloud": sorted(only_cloud),
        }


# ------------------------------------------------------------------
# Helpers para parsear front matter YAML mínimo
# ------------------------------------------------------------------

def _extract_name(content: str) -> str | None:
    """Extrae el campo 'name' del front matter YAML si existe."""
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    fm = content[3:end]
    for line in fm.splitlines():
        if line.strip().startswith("name:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return None


def _extract_tags(content: str) -> list[str]:
    """Extrae el campo 'tags' del front matter YAML si existe."""
    if not content.startswith("---"):
        return []
    end = content.find("---", 3)
    if end == -1:
        return []
    fm = content[3:end]
    in_tags = False
    tags: list[str] = []
    for line in fm.splitlines():
        stripped = line.strip()
        if stripped.startswith("tags:"):
            rest = stripped[5:].strip()
            if rest.startswith("["):
                # tags: [a, b, c]
                raw = rest.strip("[]")
                tags = [t.strip().strip('"').strip("'") for t in raw.split(",") if t.strip()]
                break
            in_tags = True
            continue
        if in_tags:
            if stripped.startswith("-"):
                tags.append(stripped[1:].strip().strip('"').strip("'"))
            else:
                break
    return tags
