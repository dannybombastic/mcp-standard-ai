from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_server.config import Settings
from mcp_server.tools import bootstrap_tools


@pytest.mark.asyncio
async def test_load_context_returns_hint_when_no_context(tmp_path: Path) -> None:
    result = await bootstrap_tools._load_context({"workspace": str(tmp_path)}, Settings())

    assert "No se encontró contexto" in result[0].text


@pytest.mark.asyncio
async def test_load_context_includes_bootstrap_and_guidelines_and_skills(tmp_path: Path) -> None:
    context = tmp_path / ".ai" / "context"
    skills = tmp_path / ".ai" / "skills"
    context.mkdir(parents=True)
    skills.mkdir(parents=True)

    (context / "MODEL_BOOTSTRAP.md").write_text("boot", encoding="utf-8")
    (context / "AI_GUIDELINES.md").write_text("guide", encoding="utf-8")
    (skills / "alpha.md").write_text("# Alpha\ncontent", encoding="utf-8")

    result = await bootstrap_tools._load_context(
        {"workspace": str(tmp_path), "include_skills": True},
        Settings(),
    )

    text = result[0].text
    assert "# MODEL BOOTSTRAP" in text
    assert "# AI GUIDELINES" in text
    assert "# SKILLS DISPONIBLES" in text
    assert "alpha" in text


@pytest.mark.asyncio
async def test_apply_skill_returns_error_with_available_when_missing(tmp_path: Path) -> None:
    skills = tmp_path / ".ai" / "skills"
    skills.mkdir(parents=True)
    (skills / "present.md").write_text("# Present", encoding="utf-8")

    result = await bootstrap_tools._apply_skill(
        {"workspace": str(tmp_path), "slug": "missing"},
        Settings(),
    )

    payload = json.loads(result[0].text)
    assert "error" in payload
    assert "present" in payload["available"]


@pytest.mark.asyncio
async def test_apply_skill_returns_markdown_when_found(tmp_path: Path) -> None:
    skills = tmp_path / ".ai" / "skills"
    skills.mkdir(parents=True)
    (skills / "demo.md").write_text("# Demo\nBody", encoding="utf-8")

    result = await bootstrap_tools._apply_skill(
        {"workspace": str(tmp_path), "slug": "demo"},
        Settings(),
    )

    assert result[0].text.startswith("# SKILL: demo")
    assert "Body" in result[0].text
