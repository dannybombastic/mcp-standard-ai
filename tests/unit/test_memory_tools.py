from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_server.config import Settings
from mcp_server.tools import memory_tools


class DummyCloudClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def aclose(self) -> None:
        return None

    async def list_sessions(self, project_slug: str | None = None, external_id: str | None = None):
        return [
            {
                "id": "session-123",
                "external_id": external_id or "chat-456",
                "title": "Session title",
                "started_at": "2024-01-01T12:00:00Z",
                "last_activity_at": "2024-01-01T12:30:00Z",
            }
        ]

    async def list_memory_entries(self, session_id: str | None = None, project_slug: str | None = None, tag: str | None = None):
        return [
            {
                "tag": "decision",
                "title": "Use OpenCode JSON",
                "content": "OpenCode imports session exports as JSON.",
                "created_at": "2024-01-01T12:05:00Z",
            },
            {
                "tag": "observation",
                "title": "Prompt files are not enough",
                "content": "OpenCode expects export JSON or a share URL.",
                "created_at": "2024-01-01T12:10:00Z",
            },
        ]


@pytest.mark.asyncio
async def test_materialize_history_for_opencode_writes_importable_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(memory_tools, "CloudClient", DummyCloudClient)

    result = await memory_tools._memory_materialize_history(
        {
            "project": "standard-ai",
            "workspace": str(tmp_path),
            "environment": "opencode",
            "max_entries": 100,
        },
        Settings(token="t", base_url="https://api.example.test"),
    )

    payload = json.loads(result[0].text)
    target = Path(payload["target_path"])

    assert payload["environment"] == "opencode"
    assert payload["import_hint"] == "opencode import <file>"
    assert target.exists()
    assert target.suffix == ".json"
    assert target.parent.name == "imports"

    exported = json.loads(target.read_text(encoding="utf-8"))
    assert exported["info"]["id"].startswith("ses_")
    assert exported["messages"][0]["info"]["role"] == "user"
    assert exported["messages"][0]["parts"][0]["type"] == "text"
    assert "OpenCode imports session exports as JSON." in exported["messages"][0]["parts"][0]["text"]


@pytest.mark.asyncio
async def test_materialize_history_for_opencode_runs_auto_import(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(memory_tools, "CloudClient", DummyCloudClient)

    called: dict[str, str] = {}

    async def fake_import(target: Path, workspace: Path) -> dict[str, object]:
        called["target"] = str(target)
        called["workspace"] = str(workspace)
        return {
            "executed": True,
            "status": "ok",
            "return_code": 0,
            "stdout": "Imported session: ses_demo",
            "stderr": "",
            "command": f"opencode import {target}",
        }

    monkeypatch.setattr(memory_tools, "_try_opencode_import", fake_import)

    result = await memory_tools._memory_materialize_history(
        {
            "project": "standard-ai",
            "workspace": str(tmp_path),
            "environment": "opencode",
            "auto_import": True,
        },
        Settings(token="t", base_url="https://api.example.test"),
    )

    payload = json.loads(result[0].text)
    assert payload["import_result"]["executed"] is True
    assert payload["import_result"]["status"] == "ok"
    assert called["workspace"] == str(tmp_path)
    assert called["target"].endswith(".json")
