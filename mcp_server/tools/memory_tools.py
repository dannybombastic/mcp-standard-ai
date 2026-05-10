"""Herramientas MCP para gestionar memoria de sesiones (Session + MemoryEntry) en la nube."""
from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from mcp_server.config import Settings
from mcp_server.cloud.client import CloudClient


def register_memory_tools(server: Server, settings: Settings) -> None:

    @server.list_tools()
    async def _list() -> list[Tool]:
        return _MEMORY_TOOLS

    @server.call_tool()
    async def _call(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        handlers = {
            "ai_session_ensure": _session_ensure,
            "ai_memory_add": _memory_add,
            "ai_memory_list": _memory_list,
            "ai_memory_materialize_history": _memory_materialize_history,
        }
        if name in handlers:
            return await handlers[name](arguments, settings)
        raise ValueError(f"Tool desconocida: {name}")


_MEMORY_TOOLS = [
    Tool(
        name="ai_session_ensure",
        description=(
            "Crea o reutiliza una Session en el backend cloud (Django), asociada a un Project. "
            "Si existe una sesión con el mismo external_id para ese project, retorna la primera."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project slug en cloud (requerido)"},
                "external_id": {"type": "string", "description": "ID externo (conversación/run). Recomendado."},
                "title": {"type": "string", "description": "Título opcional"},
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="ai_memory_add",
        description="Añade una entrada de memoria a una sesión (taggeada: observation/recommendation/decision/architecture/other).",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "UUID de Session (requerido)"},
                "tag": {
                    "type": "string",
                    "enum": ["observation", "recommendation", "decision", "architecture", "other"],
                    "default": "other",
                },
                "title": {"type": "string"},
                "content": {"type": "string", "description": "Texto de la entrada (requerido)"},
                "metadata": {"type": "object", "description": "JSON opcional (links, refs, etc.)"},
            },
            "required": ["session_id", "content"],
        },
    ),
    Tool(
        name="ai_memory_list",
        description="Lista entradas de memoria (puede filtrar por session_id, project y/o tag).",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "project": {"type": "string"},
                "tag": {"type": "string"},
            },
            "required": [],
        },
    ),
    Tool(
        name="ai_memory_materialize_history",
        description=(
            "Trae histórico de sesión desde la web (Django) y lo materializa como prompt file nativo "
            "del entorno de chat (vscode-copilot, claude) o como export JSON nativo de OpenCode."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project slug (requerido)"},
                "session_id": {"type": "string", "description": "UUID de sesión específica (opcional)"},
                "external_id": {"type": "string", "description": "ID externo de sesión (opcional)"},
                "workspace": {"type": "string", "description": "Ruta del workspace (opcional)"},
                "max_entries": {"type": "integer", "default": 200, "description": "Máximo de entradas a materializar"},
                "auto_import": {
                    "type": "boolean",
                    "default": True,
                    "description": "Si true y el entorno es opencode, ejecuta `opencode import <file>` automáticamente.",
                },
                "environment": {
                    "type": "string",
                    "enum": ["auto", "vscode-copilot", "claude", "opencode"],
                    "default": "auto",
                    "description": "Entorno de destino (auto por defecto)",
                },
            },
            "required": ["project"],
        },
    ),
]


def _detect_environment_for_workspace(workspace: Path) -> str:
    # Primero variables de entorno (ejecución real del editor)
    import os

    if os.getenv("VSCODE_PID"):
        return "vscode-copilot"
    if os.getenv("CLAUDE_ENV") or os.getenv("CLAUDE_CODE_ENV"):
        return "claude"
    if os.getenv("OPENCODE_ENV") or os.getenv("OPENCODE"):
        return "opencode"

    # Luego heurísticas de filesystem para el workspace
    if (workspace / ".vscode" / "mcp.json").exists() or (workspace / ".vscode").exists():
        return "vscode-copilot"
    if (workspace / "CLAUDE.md").exists() or (workspace / ".claude").exists():
        return "claude"
    if (workspace / ".opencode").exists() or (workspace / "OPENCODE.md").exists():
        return "opencode"

    return "unknown"


def _group_entries(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {
        "architecture": [],
        "decision": [],
        "observation": [],
        "recommendation": [],
        "other": [],
    }
    for entry in entries:
        tag = str(entry.get("tag", "other"))
        if tag not in grouped:
            tag = "other"
        grouped[tag].append(entry)
    return grouped


def _safe_stem(value: str) -> str:
    cleaned = [character if character.isalnum() or character in {"-", "_"} else "-" for character in value.strip()]
    stem = "".join(cleaned).strip("-_")
    while "--" in stem:
        stem = stem.replace("--", "-")
    return stem or "session"


def _coerce_timestamp_ms(value: Any, fallback: int | None = None) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return fallback if fallback is not None else int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        return int(parsed.timestamp() * 1000)
    return fallback if fallback is not None else int(datetime.now(tz=timezone.utc).timestamp() * 1000)


def _render_history_markdown(project: str, session: dict[str, Any], entries: list[dict[str, Any]]) -> str:
    grouped = _group_entries(entries)
    session_id = session.get("id", "")
    title = session.get("title", "")
    external_id = session.get("external_id", "")
    started_at = session.get("started_at", "")
    updated_at = session.get("last_activity_at", "")

    lines: list[str] = []
    lines.append("---")
    lines.append(f'name: "session-history-{session_id}"')
    lines.append(f'description: "Reusable session history for {project}"')
    lines.append("agent: ask")
    lines.append("---")
    lines.append("")
    lines.append("# Session History")
    lines.append("")
    lines.append(f"- project: {project}")
    lines.append(f"- session_id: {session_id}")
    if title:
        lines.append(f"- title: {title}")
    if external_id:
        lines.append(f"- external_id: {external_id}")
    if started_at:
        lines.append(f"- started_at: {started_at}")
    if updated_at:
        lines.append(f"- last_activity_at: {updated_at}")
    lines.append(f"- total_entries: {len(entries)}")
    lines.append("")

    lines.append("## AI Context Brief")
    lines.append("")
    lines.append("Use this prompt file as reusable historical context for ongoing chat sessions in this environment.")
    lines.append("")

    section_titles = [
        ("architecture", "Architecture"),
        ("decision", "Decisions"),
        ("observation", "Observations"),
        ("recommendation", "Recommendations"),
        ("other", "Other"),
    ]
    for key, title_name in section_titles:
        bucket = grouped.get(key, [])
        lines.append(f"## {title_name}")
        lines.append("")
        if not bucket:
            lines.append("- (none)")
            lines.append("")
            continue
        for entry in bucket:
            entry_title = entry.get("title") or "(untitled)"
            created = entry.get("created_at", "")
            content = (entry.get("content") or "").strip()
            lines.append(f"### {entry_title}")
            if created:
                lines.append(f"- created_at: {created}")
            lines.append("")
            lines.append(content if content else "(empty)")
            lines.append("")

    lines.append("## Raw JSON")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(entries, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _render_history_opencode_export(
    project: str,
    workspace: Path,
    session: dict[str, Any],
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    grouped = _group_entries(entries)
    session_id = str(session.get("id", ""))
    title = str(session.get("title", "") or f"Session history for {project}")
    external_id = str(session.get("external_id", "") or session_id)
    started_at = _coerce_timestamp_ms(session.get("started_at") or session.get("created_at"), fallback=0)
    updated_at = _coerce_timestamp_ms(session.get("last_activity_at") or session.get("updated_at"), fallback=started_at)
    slug = _safe_stem(str(session.get("slug") or title or external_id))

    history_markdown = _render_history_markdown(project, session, entries)
    session_message_id = f"msg_{_safe_stem(session_id)}"
    part_id = f"prt_{_safe_stem(session_id)}_history"

    return {
        "info": {
            "id": f"ses_{_safe_stem(session_id)}",
            "slug": slug,
            "projectID": project,
            "directory": str(workspace),
            "title": title,
            "version": "1.0.0",
            "time": {
                "created": started_at,
                "updated": updated_at,
            },
        },
        "messages": [
            {
                "info": {
                    "id": session_message_id,
                    "sessionID": f"ses_{_safe_stem(session_id)}",
                    "role": "user",
                    "time": {"created": updated_at},
                    "agent": "standarcloud",
                    "model": {"providerID": "standarcloud", "modelID": "history"},
                    "tools": {},
                },
                "parts": [
                    {
                        "id": part_id,
                        "sessionID": f"ses_{_safe_stem(session_id)}",
                        "messageID": session_message_id,
                        "type": "text",
                        "text": history_markdown,
                        "time": {"start": updated_at, "end": updated_at},
                    }
                ],
            }
        ],
    }


def _target_path_for_environment(workspace: Path, environment: str, session: dict[str, Any]) -> Path:
    sid = str(session.get("external_id") or session.get("id") or "session")
    safe_id = _safe_stem(sid)

    if environment == "vscode-copilot":
        return workspace / ".github" / "prompts" / f"{safe_id}.prompt.md"
    if environment == "claude":
        return workspace / ".claude" / "prompts" / f"{safe_id}.prompt.md"
    if environment == "opencode":
        return workspace / ".opencode" / "imports" / f"{safe_id}.json"
    return workspace / ".acm" / "prompts" / f"{safe_id}.prompt.md"


async def _try_opencode_import(target: Path, workspace: Path) -> dict[str, Any]:
    executable = shutil.which("opencode")
    if not executable:
        return {
            "executed": False,
            "status": "opencode_not_installed",
            "command": "opencode import <file>",
        }

    process = await asyncio.create_subprocess_exec(
        executable,
        "import",
        str(target),
        cwd=str(workspace),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    stdout_text = stdout.decode("utf-8", errors="replace").strip()
    stderr_text = stderr.decode("utf-8", errors="replace").strip()

    return {
        "executed": True,
        "status": "ok" if process.returncode == 0 else "error",
        "return_code": process.returncode,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "command": f"{executable} import {target}",
    }


async def _session_ensure(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    if not settings.token:
        return [TextContent(type="text", text=json.dumps({"error": "AI_CONTEXT_MANAGER_TOKEN no configurado."}))]

    project_slug = args["project"]
    external_id = args.get("external_id", "") or ""
    title = args.get("title", "") or ""

    client = CloudClient(settings=settings)
    try:
        # ensure project exists/owned
        await client.ensure_project(project_slug)

        if external_id:
            sessions = await client.list_sessions(project_slug=project_slug, external_id=external_id)
            if sessions:
                return [TextContent(type="text", text=json.dumps(sessions[0], indent=2, ensure_ascii=False))]

        session = await client.create_session(project_slug=project_slug, title=title, external_id=external_id)
        return [TextContent(type="text", text=json.dumps(session, indent=2, ensure_ascii=False))]
    finally:
        await client.aclose()


async def _memory_add(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    if not settings.token:
        return [TextContent(type="text", text=json.dumps({"error": "AI_CONTEXT_MANAGER_TOKEN no configurado."}))]

    session_id = args["session_id"]
    tag = args.get("tag", "other")
    title = args.get("title", "") or ""
    content = args["content"]
    metadata = args.get("metadata") or {}

    client = CloudClient(settings=settings)
    try:
        entry = await client.add_memory_entry(
            session_id=session_id,
            tag=tag,
            title=title,
            content=content,
            metadata=metadata,
        )
        return [TextContent(type="text", text=json.dumps(entry, indent=2, ensure_ascii=False))]
    finally:
        await client.aclose()


async def _memory_list(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    if not settings.token:
        return [TextContent(type="text", text=json.dumps({"error": "AI_CONTEXT_MANAGER_TOKEN no configurado."}))]

    session_id = args.get("session_id")
    project_slug = args.get("project")
    tag = args.get("tag")

    client = CloudClient(settings=settings)
    try:
        entries = await client.list_memory_entries(session_id=session_id, project_slug=project_slug, tag=tag)
        return [TextContent(type="text", text=json.dumps(entries, indent=2, ensure_ascii=False))]
    finally:
        await client.aclose()


async def _memory_materialize_history(args: dict[str, Any], settings: Settings) -> list[TextContent]:
    if not settings.token:
        return [TextContent(type="text", text=json.dumps({"error": "AI_CONTEXT_MANAGER_TOKEN no configurado."}))]

    project_slug = args["project"]
    workspace = Path(args.get("workspace") or Path.cwd()).resolve()
    max_entries = int(args.get("max_entries", 200))
    auto_import = bool(args.get("auto_import", True))
    requested_env = str(args.get("environment", "auto"))

    target_environment = _detect_environment_for_workspace(workspace) if requested_env == "auto" else requested_env

    client = CloudClient(settings=settings)
    try:
        # Resolver sesión objetivo
        session: dict[str, Any] | None = None
        if args.get("session_id"):
            sessions = await client.list_sessions(project_slug=project_slug)
            session = next((s for s in sessions if str(s.get("id")) == str(args["session_id"])), None)
        elif args.get("external_id"):
            sessions = await client.list_sessions(project_slug=project_slug, external_id=str(args["external_id"]))
            session = sessions[0] if sessions else None
        else:
            sessions = await client.list_sessions(project_slug=project_slug)
            session = sessions[0] if sessions else None

        if not session:
            return [TextContent(type="text", text=json.dumps({
                "error": "No se encontró sesión para materializar historial.",
                "project": project_slug,
            }, ensure_ascii=False))]

        entries = await client.list_memory_entries(session_id=str(session.get("id")))
        if max_entries > 0:
            entries = entries[-max_entries:]

        target = _target_path_for_environment(workspace, target_environment, session)
        target.parent.mkdir(parents=True, exist_ok=True)
        action = "created"
        if target.exists():
            action = "updated"

        if target_environment == "opencode":
            payload_object = _render_history_opencode_export(project_slug, workspace, session, entries)
            target.write_text(json.dumps(payload_object, ensure_ascii=False, indent=2), encoding="utf-8")
            import_result = await _try_opencode_import(target, workspace) if auto_import else {
                "executed": False,
                "status": "skipped",
                "reason": "auto_import_disabled",
                "command": "opencode import <file>",
            }
        else:
            markdown = _render_history_markdown(project_slug, session, entries)
            target.write_text(markdown, encoding="utf-8")
            import_result = None

        payload = {
            "status": "ok",
            "project": project_slug,
            "session_id": session.get("id"),
            "external_id": session.get("external_id"),
            "environment": target_environment,
            "entries_materialized": len(entries),
            "target_path": str(target),
            "action": action,
            "import_hint": "opencode import <file>" if target_environment == "opencode" else None,
            "import_result": import_result,
        }
        return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]
    finally:
        await client.aclose()
