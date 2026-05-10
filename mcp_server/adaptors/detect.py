"""Detectar entorno actual (Claude, VS Code/Copilot, OpenCode)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def detect_environment() -> str:
    """
    Detectar en qué entorno se está ejecutando.
    
    Retorna: "claude" | "vscode-copilot" | "opencode" | "unknown"
    """
    # Verificar si estamos en VS Code con Copilot
    # VS Code expone VSCODE_PID cuando está abierto
    if os.getenv("VSCODE_PID"):
        return "vscode-copilot"
    
    # Verificar si estamos en Claude Code
    # Claude Code expone específicas variables o tiene estructura de directorios particular
    if os.getenv("CLAUDE_ENV") or os.getenv("CLAUDE_CODE_ENV"):
        return "claude"
    
    # Verificar si .vscode/mcp.json existe (señal de que VS Code está configurado)
    workspace = Path.cwd()
    if (workspace / ".vscode" / "mcp.json").exists():
        return "vscode-copilot"
    
    # Verificar si estamos en OpenCode
    if os.getenv("OPENCODE_ENV") or os.getenv("OPENCODE"):
        return "opencode"
    
    # Por defecto, asumir VS Code/Copilot si .vscode existe
    if (workspace / ".vscode").exists():
        return "vscode-copilot"
    
    return "unknown"


def is_official_support(environment: str) -> bool:
    """Verificar si el entorno tiene soporte oficial."""
    return environment in ("claude", "vscode-copilot")
