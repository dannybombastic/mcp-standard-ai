"""MCP resources para la biblioteca de rutas y documentación oficial."""

from __future__ import annotations

import json

from mcp.server import Server
from mcp.types import Resource

from mcp_server.storage.catalog import get_official_docs, get_route_library


def register_catalog_resources(server: Server) -> None:
    @server.list_resources()
    async def _list_resources() -> list[Resource]:
        return [
            Resource(
                uri="acm://route-library",
                name="Route Library",
                description="Biblioteca de rutas oficiales y best_effort por entorno",
                mimeType="application/json",
            ),
            Resource(
                uri="acm://official-docs",
                name="Official Docs",
                description="Biblioteca de documentación oficial por entorno",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def _read_resource(uri: str) -> str:
        if uri == "acm://route-library":
            return json.dumps(get_route_library(), indent=2, ensure_ascii=False)
        if uri == "acm://official-docs":
            return json.dumps(get_official_docs(), indent=2, ensure_ascii=False)
        raise ValueError(f"URI no soportada: {uri}")
