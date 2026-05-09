"""Herramientas MCP para sincronización con StandarCloud."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from mcp_server.config import Settings
from mcp_server.storage.paths import StorageResolver
from mcp_server.storage.registry import RegistryManager
from mcp_server.cloud.client import CloudClient
from mcp_server.cloud.sync import SyncManager


def register_cloud_tools(server: Server, settings: Settings) -> None:

    @server.list_tools()
    async def _list() -> list[Tool]:
        return _CLOUD_TOOLS

    @server.call_tool()
    async def _call(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        handlers = {
            "ai_cloud_push": _cloud_push,
            "ai_cloud_pull": _cloud_pull,
            "ai_cloud_sync": _cloud_sync,
            "ai_cloud_status": _cloud_status,
        }
        if name in handlers:
            return await handlers[name](arguments, settings)
        raise ValueError(f"Tool desconocida: {name}")


_CLOUD_TOOLS = [
    Tool(
        name="ai_cloud_push",
        description="Publica assets locales en StandarCloud. Sube skills, prompts y specs al servidor.",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["skill", "prompt", "spec", "all"], "default": "all"},
                "slug": {"type": "string", "description": "Si se especifica, sube solo este asset"},
                "workspace": {"type": "string"},
            },
            "required": [],
        },
    ),
    Tool(
        name="ai_cloud_pull",
        description="Descarga assets desde StandarCloud al directorio .ai/ local.",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["skill", "prompt", "spec", "all"], "default": "all"},
                "slug": {"type": "string", "description": "Si se especifica, descarga solo este asset"},
                "workspace": {"type": "string"},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": [],
        },
    ),
    Tool(
        name="ai_cloud_sync",
        description="Sincronización bidireccional: push de cambios locales + pull de novedades remotas.",
        inputSchema={
            "type": "object",
            "properties": {
                "workspace": {"type": "string"},
                "dry_run": {"type": "boolean", "default": False, "description": "Si True, muestra qué se haría sin ejecutar"},
            },
            "required": [],
        },
    ),
    Tool(
        name="ai_cloud_status",
        description="Muestra el estado de sincronización: assets locales vs remotos, pendientes de push/pull.",
        inputSchema={
            "type": "object",
            "properties": {
                "workspace": {"type": "string"},
            },
            "required": [],
        },
    ),
]


def _make_sync(settings: Settings, paths, registry: RegistryManager) -> SyncManager:
    client = CloudClient(settings=settings)
    return SyncManager(paths=paths, registry=registry, client=client)


async def _cloud_push(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    if not settings.token:
        return [TextContent(type="text", text=json.dumps({"error": "AI_CONTEXT_MANAGER_TOKEN no configurado."}))]

    workspace = Path(args.get("workspace") or Path.cwd())
    resolver = StorageResolver(workspace)
    paths = resolver.get_paths()
    registry = RegistryManager(paths.registry)
    registry.load()

    sync = _make_sync(settings, paths, registry)
    filter_type = args.get("type", "all")
    filter_slug = args.get("slug")

    if filter_slug and filter_type != "all":
        result = [await sync.push_asset(filter_type, filter_slug)]
    else:
        result = await sync.push_all()

    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]


async def _cloud_pull(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    if not settings.token:
        return [TextContent(type="text", text=json.dumps({"error": "AI_CONTEXT_MANAGER_TOKEN no configurado."}))]

    workspace = Path(args.get("workspace") or Path.cwd())
    resolver = StorageResolver(workspace)
    paths = resolver.get_paths()
    registry = RegistryManager(paths.registry)
    registry.load()

    sync = _make_sync(settings, paths, registry)
    result = await sync.pull_all()
    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]


async def _cloud_sync(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    if not settings.token:
        return [TextContent(type="text", text=json.dumps({"error": "AI_CONTEXT_MANAGER_TOKEN no configurado."}))]

    workspace = Path(args.get("workspace") or Path.cwd())
    resolver = StorageResolver(workspace)
    paths = resolver.get_paths()
    registry = RegistryManager(paths.registry)
    registry.load()

    sync = _make_sync(settings, paths, registry)
    dry_run = args.get("dry_run", False)

    push_results = await sync.push_all(dry_run=dry_run)
    pull_results = await sync.pull_all(dry_run=dry_run)
    result = {"pushed": push_results, "pulled": pull_results}
    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]


async def _cloud_status(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    workspace = Path(args.get("workspace") or Path.cwd())
    resolver = StorageResolver(workspace)
    paths = resolver.get_paths()
    registry = RegistryManager(paths.registry)
    registry.load()

    local_assets = registry.list_all()
    synced = [a for a in local_assets if a.get("cloud_id")]
    unsynced = [a for a in local_assets if not a.get("cloud_id")]

    status_detail: dict[str, Any] = {
        "cloud_configured": bool(settings.token and settings.base_url),
        "base_url": settings.base_url,
        "total_local": len(local_assets),
        "synced_to_cloud": len(synced),
        "pending_push": len(unsynced),
        "assets": {
            "synced": [{"type": a["type"], "slug": a["slug"], "cloud_id": a["cloud_id"]} for a in synced],
            "pending": [{"type": a["type"], "slug": a["slug"]} for a in unsynced],
        },
    }

    if settings.token:
        try:
            sync = _make_sync(settings, paths, registry)
            remote_status = await sync.status()
            status_detail["remote"] = remote_status
        except Exception as e:
            status_detail["remote_error"] = str(e)

    return [TextContent(type="text", text=json.dumps(status_detail, indent=2, ensure_ascii=False))]
