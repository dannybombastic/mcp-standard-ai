"""Adaptadores por entorno para materialización de documentos nativos."""

from .base import AdapterBase
from .detect import detect_environment
from .claude import ClaudeAdapter
from .copilot import CopilotAdapter

__all__ = [
    "AdapterBase",
    "detect_environment",
    "ClaudeAdapter",
    "CopilotAdapter",
]
