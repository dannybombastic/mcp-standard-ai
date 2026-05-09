"""Registry local: índice JSON de assets en el .ai/."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REGISTRY_VERSION = 1


class RegistryManager:
    """
    Gestiona el archivo `.ai/registry.json`.

    El registry es el índice canónico de todos los assets (skills, prompts, specs)
    almacenados localmente. Permite búsquedas por tipo, nombre y tags sin leer
    cada archivo markdown individualmente.

    Estructura del JSON:
    {
      "version": 1,
      "updated_at": "<iso8601>",
      "assets": {
        "<type>/<slug>": {
          "type": "skill|prompt|spec|context",
          "slug": "...",
          "name": "...",
          "path": "...",          // relativo al .ai/
          "tags": [...],
          "cloud_id": null,       // null si solo local
          "cloud_slug": null,
          "synced_at": null,
          "checksum": "..."
        }
      }
    }
    """

    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        self._data: dict[str, Any] = {}
        self._dirty = False

    # ------------------------------------------------------------------
    # Carga y guardado
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Carga el registry desde disco. Si no existe, inicializa vacío."""
        if self.registry_path.exists():
            try:
                self._data = json.loads(self.registry_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = self._empty()
        else:
            self._data = self._empty()
        self._dirty = False

    def save(self) -> None:
        """Persiste el registry a disco."""
        self._data["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self._dirty = False

    def save_if_dirty(self) -> None:
        if self._dirty:
            self.save()

    # ------------------------------------------------------------------
    # CRUD de assets
    # ------------------------------------------------------------------

    def upsert(self, asset: dict[str, Any]) -> None:
        """Inserta o actualiza un asset en el registry."""
        key = self._key(asset["type"], asset["slug"])
        self._data.setdefault("assets", {})[key] = asset
        self._dirty = True

    def get(self, asset_type: str, slug: str) -> dict[str, Any] | None:
        key = self._key(asset_type, slug)
        return self._data.get("assets", {}).get(key)

    def remove(self, asset_type: str, slug: str) -> bool:
        key = self._key(asset_type, slug)
        assets = self._data.get("assets", {})
        if key in assets:
            del assets[key]
            self._dirty = True
            return True
        return False

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.get("assets", {}).values())

    def list_by_type(self, asset_type: str) -> list[dict[str, Any]]:
        return [a for a in self.list_all() if a.get("type") == asset_type]

    def search(self, query: str, asset_type: str | None = None) -> list[dict[str, Any]]:
        """Búsqueda simple por nombre, slug o tags."""
        q = query.lower()
        results = []
        for asset in self.list_all():
            if asset_type and asset.get("type") != asset_type:
                continue
            name_match = q in asset.get("name", "").lower()
            slug_match = q in asset.get("slug", "").lower()
            tag_match = any(q in t.lower() for t in asset.get("tags", []))
            if name_match or slug_match or tag_match:
                results.append(asset)
        return results

    def mark_synced(self, asset_type: str, slug: str, cloud_id: Any, cloud_slug: str) -> None:
        """Marca un asset como sincronizado con la nube."""
        key = self._key(asset_type, slug)
        asset = self._data.get("assets", {}).get(key)
        if asset:
            asset["cloud_id"] = cloud_id
            asset["cloud_slug"] = cloud_slug
            asset["synced_at"] = datetime.now(tz=timezone.utc).isoformat()
            self._dirty = True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _key(asset_type: str, slug: str) -> str:
        return f"{asset_type}/{slug}"

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {
            "version": REGISTRY_VERSION,
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
            "assets": {},
        }
