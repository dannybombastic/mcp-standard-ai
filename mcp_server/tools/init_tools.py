"""Herramientas MCP: status del workspace."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.types import TextContent, Tool

from mcp_server.config import Settings
from mcp_server.storage.paths import StorageResolver


# ---------------------------------------------------------------------------

_INIT_TOOLS = [
    Tool(
        name="ai_status",
        description=(
            "Muestra estado t\u00e9cnico del workspace (.acm/) y conexi\u00f3n con cloud. "
            "Qu\u00e9 archivos t\u00e9cnicos existen y si est\u00e1 configurada la nube. "
            "Recomendado usar cloud API para gestionar assets."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "workspace": {
                    "type": "string",
                    "description": "Ruta del workspace (por defecto el directorio actual)",
                },
            },
            "required": [],
        },
    ),
]




async def _ai_status(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    workspace = Path(args.get("workspace") or Path.cwd())
    resolver = StorageResolver(workspace)

    try:
        paths = resolver.get_paths()
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    if not paths.ai_dir.exists():
        return [TextContent(type="text", text=json.dumps({"initialized": False, "ai_dir": str(paths.ai_dir)}))]

    counts: dict[str, int] = {}
    for asset_type, d in [
        ("skills", paths.skills),
        ("prompts", paths.prompts),
        ("specs", paths.specs),
        ("context", paths.context),
        ("templates", paths.templates),
    ]:
        counts[asset_type] = len(list(d.glob("*.md"))) if d.exists() else 0

    result = {
        "initialized": True,
        "ai_dir": str(paths.ai_dir),
        "asset_counts": counts,
        "registry_exists": paths.registry.exists(),
        "bootstrap_exists": paths.bootstrap.exists(),
        "guidelines_exists": paths.guidelines.exists(),
        "cloud_configured": bool(settings.token and settings.base_url),
    }
    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
