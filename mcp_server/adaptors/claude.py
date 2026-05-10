"""Adaptador para entorno Claude."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import AdapterBase


class ClaudeAdapter(AdapterBase):
    """Materializa documentos para Claude Code."""

    async def materialize_documents(self, documents: dict[str, Any]) -> dict[str, str]:
        """
        Materializar documentos en:
        - CLAUDE.md (workspace root)
        - CLAUDE.local.md (workspace root, para overrides locales)
        """
        results = {}

        # Buscar documento de tipo "memory"
        memory_content = None
        for doc_id, doc in documents.items():
            if doc.get("kind") == "memory" or "claude" in doc_id.lower():
                memory_content = doc.get("content", "")
                break

        if memory_content:
            # Materializar CLAUDE.md
            claude_path = self._ensure_parent_dir(self.workspace / "CLAUDE.md")
            claude_path.write_text(memory_content, encoding="utf-8")
            results[str(claude_path)] = "created"

        return results

    async def import_native_documents(self) -> dict[str, str]:
        """Importar CLAUDE.md desde workspace."""
        documents = {}

        claude_path = self.workspace / "CLAUDE.md"
        if claude_path.exists():
            content = claude_path.read_text(encoding="utf-8")
            documents["CLAUDE"] = content

        # También verificar CLAUDE.local.md
        local_path = self.workspace / "CLAUDE.local.md"
        if local_path.exists():
            content = local_path.read_text(encoding="utf-8")
            documents["CLAUDE_LOCAL"] = content

        return documents
