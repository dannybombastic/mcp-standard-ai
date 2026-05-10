"""Herramientas para sincronización de documentos nativos."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from ..adaptors.detect import detect_environment
from ..adaptors.claude import ClaudeAdapter
from ..adaptors.copilot import CopilotAdapter


# Definición de herramientas
_DOCUMENT_SYNC_TOOLS: list[Tool] = [
    Tool(
        name="ai_detect_environment",
        description="Detectar entorno actual (claude, vscode-copilot, opencode, unknown)",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="ai_materialize_documents",
        description="Materializar documentos nativos del entorno actual (Claude.md para Claude, .github/copilot-instructions.md para Copilot, etc.). Requiere token de API.",
        inputSchema={
            "type": "object",
            "properties": {
                "documents": {
                    "type": "object",
                    "description": "Dict de doc_id -> {kind, content, ...}",
                },
            },
            "required": ["documents"],
        },
    ),
    Tool(
        name="ai_sync_environment_docs",
        description="Sincronizar documentos nativos desde la nube para el entorno actual. Detecta el entorno, obtiene documentos de la API y los materializa localmente.",
        inputSchema={
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Forzar resincronización incluso si los documentos existen",
                    "default": False,
                },
            },
            "required": [],
        },
    ),
]


def register_document_sync_tools(server: Server, workspace: Path) -> None:
    """Registrar herramientas de sincronización de documentos."""
    # Aquí se llama después desde server.py con los handlers


async def handle_materialize_documents(workspace: Path, arguments: dict[str, Any]) -> list[TextContent]:
    """Materializar documentos en ubicaciones nativas."""
    environment = detect_environment()

    if environment == "claude":
        adapter = ClaudeAdapter(workspace)
    elif environment == "vscode-copilot":
        adapter = CopilotAdapter(workspace)
    else:
        return [TextContent(type="text", text=f"Entorno no soportado: {environment}")]

    documents = arguments.get("documents", {})
    try:
        results = await adapter.materialize_documents(documents)
        text = f"Documentos materializados:\n" + "\n".join(
            f"  {path}: {status}" for path, status in results.items()
        )
        return [TextContent(type="text", text=text)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error materializando documentos: {e}")]


async def handle_detect_environment(_workspace: Path, _arguments: dict[str, Any]) -> list[TextContent]:
    """Detectar el entorno actual."""
    environment = detect_environment()
    return [TextContent(type="text", text=f"Entorno detectado: {environment}")]


async def handle_sync_environment_docs(workspace: Path, arguments: dict[str, Any]) -> list[TextContent]:
    """
    Sincronizar documentos del entorno actual desde la nube.
    
    Este es el tool principal que materializa documentos para el usuario.
    """
    environment = detect_environment()

    # Para este MVP, usamos documentos hardcodeados como ejemplo
    # En producción, estos vendrían de la API cloud
    example_documents = {
        "claude": {
            "memory": {
                "kind": "memory",
                "content": """# Claude Memory - AI Context Manager

You are an expert in context management for AI systems.

## Your Role
- Help users maintain coherent context across multiple AI conversations
- Organize knowledge and decisions for easy retrieval
- Support users in building organized AI workflows

## Key Capabilities
- Detect when context needs to be preserved
- Help organize memories by type (observation, recommendation, decision, architecture)
- Support session-based organization for different projects

## Best Practices
- Save significant discoveries immediately
- Use clear, searchable titles
- Tag memories for easy retrieval
- Review session summaries before starting new work
""",
            },
        },
        "vscode-copilot": {
            "copilot-instructions": {
                "kind": "instruction",
                "content": """# Copilot Instructions

You are GitHub Copilot, an AI pair programmer that helps developers write code.

## Behavior
- Be helpful and respectful
- Ask clarifying questions when needed
- Explain your suggestions clearly
- Keep responses concise unless detailed explanation is needed

## Code Style
- Follow the project's established patterns
- Suggest improvements that align with team standards
- Comment complex logic
- Consider performance and maintainability

## When to Ask
- Ask about edge cases you're unsure about
- Clarify requirements before implementing
- Suggest alternatives with tradeoffs
- Verify you understand the desired behavior
""",
            },
            "agent-ado-devops": {
                "kind": "agent",
                "content": """# ADO DevOps Agent

Especialista en pipelines, release automation y observabilidad de CI/CD.
""",
            },
            "agent-autonomous-solver": {
                "kind": "agent",
                "content": """# Autonomous Solver Agent

Especialista en resolución autónoma de incidencias y ejecución guiada por evidencia.
""",
            },
            "skill-azure-security": {
                "kind": "skill",
                "content": """# Azure Security Skill

Patrones de hardening, identidad, secreto y gobierno para Azure.
""",
            },
            "skill-devops-automation": {
                "kind": "skill",
                "content": """# DevOps Automation Skill

Buenas prácticas de automatización para build, test y deploy.
""",
            },
            "skill-documentation": {
                "kind": "skill",
                "content": """# Documentation Skill

Estrategias para documentación técnica clara y mantenible.
""",
            },
            "skill-terraform-patterns": {
                "kind": "skill",
                "content": """# Terraform Patterns Skill

Patrones reutilizables de IaC para módulos, estados y composición.
""",
            },
        },
    }

    documents = example_documents.get(environment, {})

    if environment == "claude":
        adapter = ClaudeAdapter(workspace)
    elif environment == "vscode-copilot":
        adapter = CopilotAdapter(workspace)
    else:
        return [
            TextContent(
                type="text",
                text=f"❌ Entorno no soportado: {environment}\n\nSoportamos: claude, vscode-copilot",
            )
        ]

    try:
        results = await adapter.materialize_documents(documents)
        if not results:
            return [TextContent(type="text", text="✅ Documentos ya sincronizados")]

        text = "✅ Documentos sincronizados:\n" + "\n".join(
            f"  ✓ {Path(path).name}: {status}" for path, status in results.items()
        )
        return [TextContent(type="text", text=text)]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error sincronizando documentos: {e}")]
