"""Herramientas MCP para gestión de assets (skills, prompts, specs)."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from mcp_server.config import Settings
from mcp_server.storage.paths import StorageResolver
from mcp_server.storage.registry import RegistryManager


def register_asset_tools(server: Server, settings: Settings) -> None:

    @server.list_tools()
    async def _list() -> list[Tool]:
        return _ASSET_TOOLS

    @server.call_tool()
    async def _call(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        handlers = {
            "ai_create_asset": _create_asset,
            "ai_get_asset": _get_asset,
            "ai_list_assets": _list_assets,
            "ai_update_asset": _update_asset,
            "ai_delete_asset": _delete_asset,
        }
        if name in handlers:
            return await handlers[name](arguments, settings)
        raise ValueError(f"Tool desconocida: {name}")


_ASSET_TOOLS = [
    Tool(
        name="ai_create_asset",
        description="Crea un nuevo asset (skill, prompt o spec) en el directorio .ai/ del workspace.",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["skill", "prompt", "spec"], "description": "Tipo de asset"},
                "slug": {"type": "string", "description": "Identificador único (kebab-case, sin espacios)"},
                "name": {"type": "string", "description": "Nombre legible del asset"},
                "content": {"type": "string", "description": "Contenido Markdown del asset"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Etiquetas para clasificar"},
                "workspace": {"type": "string", "description": "Ruta del workspace (por defecto el actual)"},
            },
            "required": ["type", "slug", "name", "content"],
        },
    ),
    Tool(
        name="ai_get_asset",
        description="Obtiene el contenido de un asset del directorio .ai/.",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["skill", "prompt", "spec"]},
                "slug": {"type": "string"},
                "workspace": {"type": "string"},
            },
            "required": ["type", "slug"],
        },
    ),
    Tool(
        name="ai_list_assets",
        description="Lista todos los assets de un tipo en el directorio .ai/.",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["skill", "prompt", "spec", "all"], "default": "all"},
                "workspace": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Filtrar por tags"},
            },
            "required": [],
        },
    ),
    Tool(
        name="ai_update_asset",
        description="Actualiza el contenido o metadatos de un asset existente.",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["skill", "prompt", "spec"]},
                "slug": {"type": "string"},
                "content": {"type": "string", "description": "Nuevo contenido (si se omite, no se cambia)"},
                "name": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "workspace": {"type": "string"},
            },
            "required": ["type", "slug"],
        },
    ),
    Tool(
        name="ai_delete_asset",
        description="Elimina un asset del directorio .ai/ local.",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["skill", "prompt", "spec"]},
                "slug": {"type": "string"},
                "workspace": {"type": "string"},
            },
            "required": ["type", "slug"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _create_asset(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    workspace = Path(args.get("workspace") or Path.cwd())
    resolver = StorageResolver(workspace)
    paths = resolver.get_paths()
    registry = RegistryManager(paths.registry)

    asset_type = args["type"]
    slug = _to_slug(args["slug"])
    name = args["name"]
    content = args["content"]
    tags = args.get("tags", [])

    asset_dir = paths.asset_dir(asset_type)
    asset_dir.mkdir(parents=True, exist_ok=True)
    dest = asset_dir / f"{slug}.md"

    if dest.exists():
        return [TextContent(type="text", text=json.dumps({"error": f"Asset ya existe: {dest}"}))]

    full_content = _build_markdown(name, asset_type, tags, content)
    dest.write_text(full_content, encoding="utf-8")

    registry.load()
    registry.upsert({
        "type": asset_type, "slug": slug, "name": name,
        "path": str(dest.relative_to(paths.ai_dir)),
        "tags": tags, "cloud_id": None, "cloud_slug": None,
        "synced_at": None, "checksum": None,
    })
    registry.save_if_dirty()

    return [TextContent(type="text", text=json.dumps({
        "created": True, "path": str(dest), "slug": slug, "type": asset_type,
    }, ensure_ascii=False))]


async def _get_asset(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    workspace = Path(args.get("workspace") or Path.cwd())
    resolver = StorageResolver(workspace)
    paths = resolver.get_paths()

    asset_type = args["type"]
    slug = args["slug"]
    dest = paths.asset_dir(asset_type) / f"{slug}.md"

    if not dest.exists():
        return [TextContent(type="text", text=json.dumps({"error": f"No encontrado: {dest}"}))]

    content = dest.read_text(encoding="utf-8")
    return [TextContent(type="text", text=content)]


async def _list_assets(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    workspace = Path(args.get("workspace") or Path.cwd())
    resolver = StorageResolver(workspace)
    paths = resolver.get_paths()
    registry = RegistryManager(paths.registry)
    registry.load()

    filter_type = args.get("type", "all")
    filter_tags = set(args.get("tags") or [])

    types = ["skill", "prompt", "spec"] if filter_type == "all" else [filter_type]
    result: list[dict[str, Any]] = []

    for atype in types:
        for entry in registry.list_by_type(atype):
            if filter_tags and not filter_tags.intersection(entry.get("tags", [])):
                continue
            result.append(entry)

    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]


async def _update_asset(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    workspace = Path(args.get("workspace") or Path.cwd())
    resolver = StorageResolver(workspace)
    paths = resolver.get_paths()
    registry = RegistryManager(paths.registry)

    asset_type = args["type"]
    slug = args["slug"]
    dest = paths.asset_dir(asset_type) / f"{slug}.md"

    if not dest.exists():
        return [TextContent(type="text", text=json.dumps({"error": f"No encontrado: {dest}"}))]

    existing_content = dest.read_text(encoding="utf-8")
    name = args.get("name") or _extract_front_matter_field(existing_content, "name") or slug
    tags = args.get("tags") or _extract_front_matter_tags(existing_content)
    body = args.get("content") or _strip_front_matter(existing_content)

    full_content = _build_markdown(name, asset_type, tags, body)
    dest.write_text(full_content, encoding="utf-8")

    registry.load()
    registry.upsert({
        "type": asset_type, "slug": slug, "name": name,
        "path": str(dest.relative_to(paths.ai_dir)),
        "tags": tags, "cloud_id": None, "cloud_slug": None,
        "synced_at": None, "checksum": None,
    })
    registry.save_if_dirty()

    return [TextContent(type="text", text=json.dumps({"updated": True, "slug": slug, "type": asset_type}))]


async def _delete_asset(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    workspace = Path(args.get("workspace") or Path.cwd())
    resolver = StorageResolver(workspace)
    paths = resolver.get_paths()
    registry = RegistryManager(paths.registry)

    asset_type = args["type"]
    slug = args["slug"]
    dest = paths.asset_dir(asset_type) / f"{slug}.md"

    if not dest.exists():
        return [TextContent(type="text", text=json.dumps({"error": f"No encontrado: {dest}"}))]

    dest.unlink()
    registry.load()
    registry.remove(asset_type, slug)
    registry.save_if_dirty()

    return [TextContent(type="text", text=json.dumps({"deleted": True, "slug": slug, "type": asset_type}))]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_slug(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _build_markdown(name: str, asset_type: str, tags: list[str], body: str) -> str:
    tags_yaml = ", ".join(f'"{t}"' for t in tags) if tags else ""
    fm = f"---\ntype: {asset_type}\nname: {name}\n"
    if tags_yaml:
        fm += f"tags: [{tags_yaml}]\n"
    fm += "---\n\n"
    return fm + body.lstrip("\n")


def _extract_front_matter_field(content: str, field: str) -> str | None:
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    for line in content[3:end].splitlines():
        if line.strip().startswith(f"{field}:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return None


def _extract_front_matter_tags(content: str) -> list[str]:
    if not content.startswith("---"):
        return []
    end = content.find("---", 3)
    if end == -1:
        return []
    fm = content[3:end]
    for line in fm.splitlines():
        if line.strip().startswith("tags:"):
            rest = line.split(":", 1)[1].strip()
            if rest.startswith("["):
                raw = rest.strip("[]")
                return [t.strip().strip('"').strip("'") for t in raw.split(",") if t.strip()]
    return []


def _strip_front_matter(content: str) -> str:
    if not content.startswith("---"):
        return content
    end = content.find("---", 3)
    if end == -1:
        return content
    return content[end + 3:].lstrip("\n")
