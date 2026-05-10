"""Biblioteca de documentación oficial y rutas por entorno."""

from __future__ import annotations

from copy import deepcopy


ROUTE_LIBRARY: dict[str, dict[str, object]] = {
    "claude": {
        "support_level": "official",
        "documents": [
            {"kind": "memory", "path": "CLAUDE.md", "support_level": "official"},
            {"kind": "memory", "path": "~/.claude/CLAUDE.md", "support_level": "official"},
            {"kind": "memory", "path": "CLAUDE.local.md", "support_level": "official"},
        ],
        "sessions": [
            {"kind": "session", "path": "local-session-store", "support_level": "best_effort"},
        ],
    },
    "vscode-copilot": {
        "support_level": "official",
        "documents": [
            {"kind": "instruction", "path": ".github/copilot-instructions.md", "support_level": "official"},
            {"kind": "instruction", "path": "AGENTS.md", "support_level": "official"},
            {"kind": "prompt", "path": ".github/prompts/*.prompt.md", "support_level": "official"},
            {"kind": "skill", "path": ".github/skills/*/SKILL.md", "support_level": "official"},
        ],
        "sessions": [
            {"kind": "session", "path": "workspaceStorage/*", "support_level": "best_effort"},
        ],
    },
    "opencode": {
        "support_level": "best_effort",
        "documents": [
            {"kind": "instruction", "path": "AGENTS.md", "support_level": "documented-compatible"},
            {"kind": "prompt", "path": "*.prompt.md", "support_level": "best_effort"},
        ],
        "sessions": [
            {"kind": "session", "path": "opencode-session-store", "support_level": "best_effort"},
        ],
    },
}

OFFICIAL_DOCS: dict[str, list[dict[str, str]]] = {
    "claude": [
        {"title": "Claude Code memory", "url": "https://docs.anthropic.com/en/docs/claude-code/memory"},
    ],
    "vscode-copilot": [
        {"title": "Copilot custom instructions", "url": "https://code.visualstudio.com/docs/copilot/customization/custom-instructions"},
        {"title": "Copilot chat sessions", "url": "https://code.visualstudio.com/docs/copilot/chat/chat-sessions"},
        {"title": "MCP configuration", "url": "https://code.visualstudio.com/docs/copilot/reference/mcp-configuration"},
        {"title": "Copilot skills", "url": "https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/create-skills"},
    ],
    "opencode": [
        {"title": "OpenCode troubleshooting", "url": "https://dev.opencode.ai/docs/troubleshooting/"},
        {"title": "OpenCode MCP servers", "url": "https://thdxr.dev.opencode.ai/docs/mcp-servers/"},
    ],
}


def get_route_library() -> dict[str, dict[str, object]]:
    return deepcopy(ROUTE_LIBRARY)


def get_official_docs() -> dict[str, list[dict[str, str]]]:
    return deepcopy(OFFICIAL_DOCS)
