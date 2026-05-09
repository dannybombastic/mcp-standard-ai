"""Herramientas MCP para inicializar el directorio .ai/ en un workspace."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from mcp_server.config import Settings
from mcp_server.storage.paths import StorageResolver


def register_init_tools(server: Server, settings: Settings) -> None:
    """Registra las herramientas de inicialización en el servidor MCP."""

    @server.list_tools()
    async def _list() -> list[Tool]:
        return _INIT_TOOLS

    @server.call_tool()
    async def _call(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "ai_init":
            return await _ai_init(arguments, settings)
        if name == "ai_status":
            return await _ai_status(arguments, settings)
        raise ValueError(f"Tool desconocida: {name}")


# ---------------------------------------------------------------------------

_INIT_TOOLS = [
    Tool(
        name="ai_init",
        description=(
            "Inicializa el directorio .ai/ en el workspace actual. "
            "Crea la estructura de carpetas estándar (context/, skills/, prompts/, specs/, templates/) "
            "y los archivos de contexto base (MODEL_BOOTSTRAP.md, AI_GUIDELINES.md)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "workspace": {
                    "type": "string",
                    "description": "Ruta del workspace a inicializar (por defecto el directorio actual)",
                },
                "mode": {
                    "type": "string",
                    "enum": ["workspace", "global"],
                    "default": "workspace",
                    "description": "workspace: .ai/ dentro del proyecto; global: ~/.ai/projects/<key>/",
                },
                "project_key": {
                    "type": "string",
                    "description": "Clave única del proyecto (requerida si mode=global)",
                },
                "force": {
                    "type": "boolean",
                    "default": False,
                    "description": "Si True, sobreescribe archivos existentes",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="ai_status",
        description=(
            "Muestra el estado del directorio .ai/ del workspace: "
            "qué archivos existen, cuántos assets hay por tipo, y si está configurada la nube."
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


async def _ai_init(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    workspace = Path(args.get("workspace") or Path.cwd())
    mode = args.get("mode", "workspace")
    project_key = args.get("project_key")
    force = args.get("force", False)

    resolver = StorageResolver(workspace)
    paths = resolver.get_paths(mode=mode, project_key=project_key)
    paths.create_all()

    created: list[str] = []

    # Archivos de contexto base
    bootstrap_tpl = _BOOTSTRAP_TEMPLATE
    guidelines_tpl = _GUIDELINES_TEMPLATE

    for dest, content in [
        (paths.bootstrap, bootstrap_tpl),
        (paths.guidelines, guidelines_tpl),
    ]:
        if not dest.exists() or force:
            dest.write_text(content, encoding="utf-8")
            created.append(str(dest))

    # registry.json inicial
    if not paths.registry.exists() or force:
        paths.registry.write_text(
            json.dumps({"version": 1, "assets": {}}, indent=2),
            encoding="utf-8",
        )
        created.append(str(paths.registry))

    summary = {
        "ai_dir": str(paths.ai_dir),
        "mode": mode,
        "created_files": created,
        "status": "initialized" if created else "already_exists",
    }
    return [TextContent(type="text", text=json.dumps(summary, indent=2, ensure_ascii=False))]


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


# ---------------------------------------------------------------------------
# Plantillas mínimas
# ---------------------------------------------------------------------------

_BOOTSTRAP_TEMPLATE = """\
---
type: context
name: Model Bootstrap
description: Instrucciones de arranque para el modelo IA en este proyecto
---

# Model Bootstrap

Este archivo es cargado automáticamente por el servidor MCP al inicio de cada sesión.
Define el contexto base, convenciones y comportamiento esperado del modelo en este workspace.

## Proyecto

<!-- Describe brevemente el proyecto -->

## Stack Tecnológico

<!-- Lista el stack: lenguajes, frameworks, herramientas principales -->

## Convenciones de Código

<!-- Nombrado, estilo, patrones preferidos -->

## Contexto Adicional

<!-- Cualquier información relevante para el modelo -->
"""

_GUIDELINES_TEMPLATE = """\
---
type: context
name: AI Guidelines
description: Guías de comportamiento para el asistente IA en este proyecto
---

# AI Guidelines

## Principios Generales

- Responde siempre en el idioma del usuario
- Prioriza la claridad y la legibilidad del código
- Sigue las convenciones establecidas en MODEL_BOOTSTRAP.md

## Qué hacer

- Usa los skills disponibles en `.ai/skills/` para tareas recurrentes
- Consulta las specs en `.ai/specs/` antes de proponer arquitecturas
- Propón mejoras cuando detectes deuda técnica

## Qué evitar

- No inventes APIs o funciones que no existan en el proyecto
- No omitas manejo de errores en código de producción
- No uses librerías externas sin consultar primero
"""
