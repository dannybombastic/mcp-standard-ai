"""MCP Resources: DEPRECATED. Expone assets técnicos locales. Usa cloud API para contenido."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from pydantic import AnyUrl
from mcp.server import Server
from mcp.types import Resource, TextContent

from mcp_server.config import Settings
from mcp_server.storage.paths import StorageResolver
from mcp_server.storage.registry import RegistryManager

logger = logging.getLogger(__name__)

_ASSET_TYPES = ("skill", "prompt", "spec")


def register_asset_resources(server: Server, settings: Settings) -> None:
    """Registra los MCP Resources para los assets del workspace."""

    @server.list_resources()
    async def _list_resources() -> list[Resource]:
        """Devuelve la lista de recursos técnicos en .acm/ del workspace (legacy)."""
        workspace = Path.cwd()
        resolver = StorageResolver(workspace)
        paths = resolver.get_paths()

        if not paths.ai_dir.exists():
            return []

        registry = RegistryManager(paths.registry)
        registry.load()

        resources: list[Resource] = []
        for asset in registry.list_all():
            atype = asset.get("type", "asset")
            slug = asset.get("slug", "")
            name = asset.get("name", slug)
            uri = cast("AnyUrl", f"standarcloud://{atype}/{slug}")
            resources.append(
                Resource(
                    uri=uri,
                    name=f"[{atype}] {name}",
                    description=f"Asset de tipo '{atype}' con slug '{slug}'",
                    mimeType="text/markdown",
                )
            )

        return resources

    @server.read_resource()
    async def _read_resource(uri: str) -> str:
        """Lee el contenido de un asset por su URI standarcloud://type/slug."""
        workspace = Path.cwd()
        resolver = StorageResolver(workspace)
        paths = resolver.get_paths()

        # Parsear URI: standarcloud://skill/my-slug
        if not uri.startswith("standarcloud://"):
            raise ValueError(f"URI no soportada: {uri}")

        rest = uri[len("standarcloud://"):]
        parts = rest.split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"URI malformada: {uri}")

        asset_type, slug = parts[0], parts[1]
        if asset_type not in _ASSET_TYPES:
            raise ValueError(f"Tipo de asset desconocido: {asset_type}")

        asset_path = paths.asset_dir(asset_type) / f"{slug}.md"
        if not asset_path.exists():
            raise FileNotFoundError(f"Asset no encontrado: {asset_path}")

        return asset_path.read_text(encoding="utf-8")
