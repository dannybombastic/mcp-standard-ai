"""SyncManager: DEPRECATED. Sincronización heredada. Use cloud API directamente."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import os

from mcp_server.cloud.client import CloudClient
from mcp_server.storage.acm_paths import AcmPaths
from mcp_server.storage.paths import AIPaths
from mcp_server.storage.registry import RegistryManager

logger = logging.getLogger(__name__)


def _prune_empty_parents(start_dir: Path, stop_at: Path) -> None:
    """
    Elimina directorios vacíos hacia arriba desde start_dir hasta stop_at (incluido stop_at como límite).
    No borra stop_at, solo se detiene al llegar.
    """
    current = start_dir
    stop_at = stop_at.resolve()
    while True:
        if not current.exists() or not current.is_dir():
            break
        if current.resolve() == stop_at:
            break
        try:
            next(current.iterdir())
            break  # no está vacío
        except StopIteration:
            current.rmdir()
            current = current.parent
            continue


class SyncManager:
    """
    Orquesta la sincronización bidireccional entre el directorio  local
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
        self._acm = AcmPaths(self.paths.ai_dir.parent)

    def _record_sync_state(self, stage: str, payload: dict[str, Any]) -> None:
        self._acm.create_all()
        state = {
            "version": 1,
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
            "stage": stage,
            "project_root": str(self.paths.ai_dir.parent),
            "payload": payload,
        }
        self._acm.sync_state.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

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
            # Política: el MCP solo sincroniza metainfo en Markdown.
            # No debe subir JSON u otros formatos de configuración del editor.
            for md_file in sorted(asset_dir.rglob("*.md")):
                result = await self._push_file(md_file, asset_type, project_slug, dry_run)
                results.append(result)

        if not dry_run:
            self.registry.save_if_dirty()
        self._record_sync_state("push_all", {"dry_run": dry_run, "results": results})

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

    async def pull_all(
        self,
        project_slug: str | None = None,
        dry_run: bool = False,
        mirror_delete: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Descarga todos los assets de la nube que no están en local
        o que tienen una versión más nueva.

        Si mirror_delete=True, aplica modo espejo:
        - elimina localmente los assets (y entradas de registry) que ya no existen en cloud
        - limpia ficheros técnicos huérfanos dentro de .acm/ para ese tipo
        """
        self.registry.load()
        results: list[dict[str, Any]] = []

        # 1) Pull/Update desde cloud
        cloud_index: dict[str, dict[str, Any]] = {}
        for asset_type in ["skill", "prompt", "spec"]:
            cloud_assets = await self.client.list_assets(asset_type, project_slug=project_slug)
            for cloud_asset in cloud_assets:
                remote_path = cloud_asset.get("path", "") or ""
                slug = Path(remote_path).stem if remote_path else ""
                if slug:
                    cloud_index[f"{asset_type}/{slug}"] = cloud_asset

                result = await self._pull_asset(cloud_asset, asset_type, dry_run)
                results.append(result)

        # 2) Mirror delete: borrar local si no existe en cloud
        if mirror_delete:
            deletes = await self._mirror_delete_missing(cloud_index=cloud_index, dry_run=dry_run)
            results.extend(deletes)

        if not dry_run:
            self.registry.save_if_dirty()
        self._record_sync_state("pull_all", {"dry_run": dry_run, "mirror_delete": mirror_delete, "results": results})

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
    # Mirror delete helpers
    # ------------------------------------------------------------------

    async def _mirror_delete_missing(
        self,
        cloud_index: dict[str, dict[str, Any]],
        dry_run: bool,
    ) -> list[dict[str, Any]]:
        """
        Elimina assets locales que ya no existen en cloud (modo espejo).

        cloud_index usa keys tipo '{type}/{slug}'.
        """
        results: list[dict[str, Any]] = []

        # borrar entradas del registry (y sus ficheros) que no están en cloud
        local_assets = list(self.registry.list_all())
        for a in local_assets:
            key = f"{a.get('type')}/{a.get('slug')}"
            if key in cloud_index:
                continue

            asset_type = a.get("type")
            slug = a.get("slug")
            rel_path = a.get("path") or ""
            target_path = (self.paths.ai_dir / rel_path) if rel_path else (self.paths.asset_dir(asset_type) / f"{slug}.md")

            if dry_run:
                results.append({"slug": slug, "type": asset_type, "action": "delete", "status": "dry_run", "path": str(target_path)})
                continue

            try:
                if target_path.exists():
                    target_path.unlink()
                # limpiar carpetas vacías hacia arriba hasta el asset_dir
                _prune_empty_parents(target_path.parent, stop_at=self.paths.asset_dir(asset_type))
            except Exception as e:
                results.append({"slug": slug, "type": asset_type, "action": "delete", "status": f"error: {e}"})
                continue

            # remover del registry (si existe método), si no, marcamos como tombstone via upsert vacío
            if hasattr(self.registry, "delete"):
                try:
                    self.registry.delete(asset_type, slug)
                except Exception:
                    pass
            else:
                # fallback: dejar upsert sin cloud_id para que no lo considere synced
                self.registry.upsert({
                    "type": asset_type,
                    "slug": slug,
                    "name": a.get("name") or slug,
                    "path": rel_path,
                    "tags": a.get("tags") or [],
                    "cloud_id": None,
                    "cloud_slug": None,
                    "synced_at": None,
                    "checksum": None,
                })

            results.append({"slug": slug, "type": asset_type, "action": "delete", "status": "ok"})

        # borrar ficheros huérfanos que existan en disco dentro de cada tipo y no estén en registry
        for asset_type in ["skill", "prompt", "spec"]:
            asset_dir = self.paths.asset_dir(asset_type)
            if not asset_dir.exists():
                continue

            keep_files: set[Path] = set()
            for a in self.registry.list_all():
                if a.get("type") != asset_type:
                    continue
                rel_path = a.get("path") or ""
                if rel_path:
                    keep_files.add(self.paths.ai_dir / rel_path)

            for p in asset_dir.rglob("*"):
                if not p.is_file():
                    continue
                if p.suffix.lower() not in {".md", ".json"} and asset_type in {"skill", "prompt", "spec"}:
                    # normalmente todo es .md pero no bloqueamos por si hay json adjunto
                    pass
                if p not in keep_files:
                    if dry_run:
                        results.append({"slug": p.stem, "type": asset_type, "action": "delete_file", "status": "dry_run", "path": str(p)})
                        continue
                    try:
                        p.unlink()
                        _prune_empty_parents(p.parent, stop_at=asset_dir)
                        results.append({"slug": p.stem, "type": asset_type, "action": "delete_file", "status": "ok", "path": str(p)})
                    except Exception as e:
                        results.append({"slug": p.stem, "type": asset_type, "action": "delete_file", "status": f"error: {e}", "path": str(p)})

        return results

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

        status = {
            "local_count": len(local_keys),
            "cloud_count": len(cloud_keys),
            "synced": sorted(synced),
            "only_local": sorted(only_local),
            "only_cloud": sorted(only_cloud),
        }
        self._record_sync_state("status", status)
        return status


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
