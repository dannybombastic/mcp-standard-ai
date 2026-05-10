"""Adaptador para entorno VS Code / Copilot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import AdapterBase


class CopilotAdapter(AdapterBase):
    """Materializa documentos para VS Code Copilot."""

    async def materialize_documents(self, documents: dict[str, Any]) -> dict[str, str]:
        """
        Materializar documentos en `.github/` con convención de Copilot:
        - .github/copilot-instructions.md
        - .github/agents/*.agent.md
        - .github/skills/*.skill.md
        """
        results: dict[str, str] = {}

        for doc_id, doc in documents.items():
            content = doc.get("content", "")
            if not content:
                continue

            explicit_path = doc.get("target_path")
            if explicit_path:
                target = self.workspace / explicit_path
            else:
                target = self._resolve_target_path(doc_id, doc)

            target = self._ensure_parent_dir(target)
            status = "created"
            if target.exists() and target.read_text(encoding="utf-8") == content:
                results[str(target)] = "skipped"
                continue
            if target.exists():
                status = "updated"

            target.write_text(content, encoding="utf-8")
            results[str(target)] = status

        return results

    def _resolve_target_path(self, doc_id: str, doc: dict[str, Any]) -> Path:
        kind = str(doc.get("kind", "")).lower()
        doc_id_normalized = doc_id.strip().lower().replace(" ", "-").replace("_", "-")
        github_root = self.workspace / ".github"

        if kind == "instruction" or "copilot-instructions" in doc_id_normalized:
            return github_root / "copilot-instructions.md"

        if kind == "agent" or doc_id_normalized.startswith("agent-"):
            name = doc_id_normalized.removeprefix("agent-")
            if not name.endswith(".agent.md"):
                name = f"{name}.agent.md"
            return github_root / "agents" / name

        if kind == "skill" or doc_id_normalized.startswith("skill-"):
            name = doc_id_normalized.removeprefix("skill-")
            if not name.endswith(".skill.md"):
                name = f"{name}.skill.md"
            return github_root / "skills" / name

        return github_root / f"{doc_id_normalized}.md"

    async def import_native_documents(self) -> dict[str, str]:
        """Importar documentos nativos de Copilot desde workspace."""
        documents: dict[str, str] = {}

        # Importar .github/copilot-instructions.md
        copilot_path = self.workspace / ".github" / "copilot-instructions.md"
        if copilot_path.exists():
            content = copilot_path.read_text(encoding="utf-8")
            documents["copilot-instructions"] = content

        agents_dir = self.workspace / ".github" / "agents"
        if agents_dir.exists():
            for path in sorted(agents_dir.glob("*.agent.md")):
                documents[f"agent-{path.stem.replace('.agent', '')}"] = path.read_text(encoding="utf-8")

        skills_dir = self.workspace / ".github" / "skills"
        if skills_dir.exists():
            for path in sorted(skills_dir.glob("*.skill.md")):
                documents[f"skill-{path.stem.replace('.skill', '')}"] = path.read_text(encoding="utf-8")

        return documents
