"""Herramientas MCP para leer y aplicar el contexto de arranque (.ai/context/)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from mcp_server.config import Settings
from mcp_server.storage.paths import StorageResolver


def register_bootstrap_tools(server: Server, settings: Settings) -> None:

    @server.list_tools()
    async def _list() -> list[Tool]:
        return _BOOTSTRAP_TOOLS

    @server.call_tool()
    async def _call(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "ai_load_context":
            return await _load_context(arguments, settings)
        if name == "ai_apply_skill":
            return await _apply_skill(arguments, settings)
        raise ValueError(f"Tool desconocida: {name}")


_BOOTSTRAP_TOOLS = [
    Tool(
        name="ai_load_context",
        description=(
            "Carga el contexto completo del directorio .ai/ del workspace. "
            "Lee MODEL_BOOTSTRAP.md, AI_GUIDELINES.md y todos los archivos de context/. "
            "Debe llamarse al inicio de cada sesión para que el modelo tenga el contexto del proyecto."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Ruta del workspace"},
                "include_skills": {"type": "boolean", "default": False, "description": "Incluir también el índice de skills disponibles"},
            },
            "required": [],
        },
    ),
    Tool(
        name="ai_apply_skill",
        description=(
            "Carga e inyecta el contenido de un skill específico para aplicarlo en la conversación actual. "
            "Útil para activar un skill puntualmente sin cargar todo el contexto."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug del skill a aplicar"},
                "workspace": {"type": "string"},
            },
            "required": ["slug"],
        },
    ),
]


async def _load_context(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    workspace = Path(args.get("workspace") or Path.cwd())
    resolver = StorageResolver(workspace)

    try:
        paths = resolver.get_paths()
    except Exception as e:
        return [TextContent(type="text", text=f"Error al resolver .ai/: {e}")]

    sections: list[str] = []

    # 1. MODEL_BOOTSTRAP.md
    if paths.bootstrap.exists():
        sections.append(f"# MODEL BOOTSTRAP\n\n{paths.bootstrap.read_text(encoding='utf-8')}")

    # 2. AI_GUIDELINES.md
    if paths.guidelines.exists():
        sections.append(f"# AI GUIDELINES\n\n{paths.guidelines.read_text(encoding='utf-8')}")

    # 3. Archivos adicionales en context/
    if paths.context.exists():
        for md in sorted(paths.context.glob("*.md")):
            if md.name not in ("MODEL_BOOTSTRAP.md", "AI_GUIDELINES.md"):
                sections.append(f"# CONTEXT: {md.stem}\n\n{md.read_text(encoding='utf-8')}")

    # 4. Índice de skills (opcional)
    if args.get("include_skills") and paths.skills.exists():
        skill_index: list[str] = []
        for md in sorted(paths.skills.glob("*.md")):
            first_line = md.read_text(encoding="utf-8").splitlines()
            title = next((l.lstrip("# ") for l in first_line if l.startswith("#")), md.stem)
            skill_index.append(f"- **{md.stem}**: {title}")
        if skill_index:
            sections.append("# SKILLS DISPONIBLES\n\n" + "\n".join(skill_index))

    if not sections:
        return [TextContent(type="text", text=(
            "No se encontró contexto en .ai/. "
            "Ejecuta `ai_init` para inicializar el directorio de contexto."
        ))]

    return [TextContent(type="text", text="\n\n---\n\n".join(sections))]


async def _apply_skill(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    workspace = Path(args.get("workspace") or Path.cwd())
    resolver = StorageResolver(workspace)

    try:
        paths = resolver.get_paths()
    except Exception as e:
        return [TextContent(type="text", text=f"Error al resolver .ai/: {e}")]

    slug = args["slug"]
    skill_file = paths.skills / f"{slug}.md"

    if not skill_file.exists():
        available = [f.stem for f in paths.skills.glob("*.md")] if paths.skills.exists() else []
        return [TextContent(type="text", text=json.dumps({
            "error": f"Skill '{slug}' no encontrado.",
            "available": available,
        }, ensure_ascii=False))]

    content = skill_file.read_text(encoding="utf-8")
    return [TextContent(type="text", text=f"# SKILL: {slug}\n\n{content}")]
