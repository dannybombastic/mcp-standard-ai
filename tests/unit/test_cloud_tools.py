from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_server.config import Settings
from mcp_server.tools import cloud_tools


class DummySync:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def push_asset(self, asset_type: str, slug: str, project_slug: str | None = None):
        self.calls.append(("push_asset", (asset_type, slug, project_slug)))
        return {"ok": True, "mode": "single"}

    async def push_all(self, project_slug: str | None = None, dry_run: bool = False):
        self.calls.append(("push_all", (project_slug, dry_run)))
        return [{"ok": True, "dry_run": dry_run}]

    async def pull_all(self, project_slug: str | None = None, dry_run: bool = False, mirror_delete: bool = False):
        self.calls.append(("pull_all", (project_slug, dry_run, mirror_delete)))
        return [{"ok": True, "dry_run": dry_run}]

    async def status(self):
        self.calls.append(("status", None))
        return {"remote_total": 1}


class DummyCloudClient:
    remote_assets: dict[str, list[dict[str, object]]] = {"skill": [], "prompt": [], "spec": []}

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def list_assets(self, asset_type: str, project_slug: str | None = None):
        return self.remote_assets.get(asset_type, [])

    async def push_asset_content(self, **kwargs):
        raise AssertionError("push_asset_content should not be called when content is unchanged")


def _write_project_binding(tmp_path: Path) -> None:
    acm = tmp_path / ".acm"
    acm.mkdir(parents=True, exist_ok=True)
    (acm / "project.json").write_text(json.dumps({"project_slug": "standard-ai"}), encoding="utf-8")


@pytest.mark.asyncio
async def test_cloud_push_requires_token(tmp_path: Path) -> None:
    result = await cloud_tools._cloud_push({"workspace": str(tmp_path)}, Settings(token="", base_url="x"))

    payload = json.loads(result[0].text)
    assert "error" in payload


@pytest.mark.asyncio
async def test_cloud_sync_uses_make_sync_and_respects_dry_run(tmp_path: Path, monkeypatch) -> None:
    _write_project_binding(tmp_path)
    dummy = DummySync()
    monkeypatch.setattr(cloud_tools, "_make_sync", lambda settings, paths, registry: dummy)

    result = await cloud_tools._cloud_sync(
        {"workspace": str(tmp_path), "dry_run": True},
        Settings(token="t", base_url="https://api.example.test"),
    )

    payload = json.loads(result[0].text)
    assert payload["pushed"] == []
    assert payload["pulled"][0]["dry_run"] is True
    assert payload["push_enabled"] is False


@pytest.mark.asyncio
async def test_cloud_push_single_asset_route(tmp_path: Path, monkeypatch) -> None:
    _write_project_binding(tmp_path)
    dummy = DummySync()
    monkeypatch.setattr(cloud_tools, "_make_sync", lambda settings, paths, registry: dummy)

    result = await cloud_tools._cloud_push(
        {"workspace": str(tmp_path), "type": "skill", "slug": "demo"},
        Settings(token="t", base_url="https://api.example.test"),
    )

    payload = json.loads(result[0].text)
    assert payload[0]["mode"] == "single"
    assert ("push_asset", ("skill", "demo", "standard-ai")) in dummy.calls


@pytest.mark.asyncio
async def test_cloud_status_reports_pending_and_synced(tmp_path: Path, monkeypatch) -> None:
    _write_project_binding(tmp_path)
    acm = tmp_path / ".acm"
    (acm / "registry.json").write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "now",
                "assets": {
                    "skill/a": {"type": "skill", "slug": "a", "cloud_id": None},
                    "skill/b": {"type": "skill", "slug": "b", "cloud_id": "cid"},
                },
            }
        ),
        encoding="utf-8",
    )

    dummy = DummySync()
    monkeypatch.setattr(cloud_tools, "_make_sync", lambda settings, paths, registry: dummy)

    result = await cloud_tools._cloud_status(
        {"workspace": str(tmp_path)},
        Settings(token="t", base_url="https://api.example.test"),
    )

    payload = json.loads(result[0].text)
    assert payload["total_local"] == 2
    assert payload["synced_to_cloud"] == 1
    assert payload["pending_push"] == 1
    assert payload["remote"]["remote_total"] == 1


@pytest.mark.asyncio
async def test_push_copilot_native_assets_skips_when_remote_content_matches(tmp_path: Path, monkeypatch) -> None:
    github = tmp_path / ".github"
    github.mkdir(parents=True)
    local_file = github / "copilot-instructions.md"
    local_file.write_text("same-content", encoding="utf-8")

    DummyCloudClient.remote_assets = {
        "skill": [],
        "prompt": [
            {
                "id": "asset-1",
                "path": ".github/copilot-instructions.md",
                "content": "same-content",
            }
        ],
        "spec": [],
    }
    monkeypatch.setattr(cloud_tools, "CloudClient", DummyCloudClient)

    result = await cloud_tools._push_copilot_native_assets(
        workspace=tmp_path,
        settings=Settings(token="t", base_url="https://api.example.test"),
        project_slug="standard-ai",
        filter_type="all",
        filter_slug=None,
    )

    assert result[0]["action"] == "skip"
    assert result[0]["status"] == "no_changes"
    assert result[0]["cloud_id"] == "asset-1"


@pytest.mark.asyncio
async def test_cloud_status_counts_top_level_github_markdown_assets(tmp_path: Path, monkeypatch) -> None:
    _write_project_binding(tmp_path)
    github = tmp_path / ".github"
    github.mkdir(parents=True)
    (github / "JavaScript.md").write_text("# Autonomous JavaScript skill\n", encoding="utf-8")

    DummyCloudClient.remote_assets = {
        "skill": [
            {
                "id": "asset-js",
                "asset_type": "skill",
                "path": ".github/JavaScript.md",
                "content": "# Autonomous JavaScript skill\n",
            }
        ],
        "prompt": [],
        "spec": [],
    }
    monkeypatch.setattr(cloud_tools, "CloudClient", DummyCloudClient)
    monkeypatch.setattr(cloud_tools, "detect_environment", lambda: "vscode-copilot")

    result = await cloud_tools._cloud_status(
        {"workspace": str(tmp_path)},
        Settings(token="t", base_url="https://api.example.test"),
    )

    payload = json.loads(result[0].text)
    assert payload["total_local"] == 1
    assert payload["synced_to_cloud"] == 1
    assert payload["pending_push"] == 0
    assert payload["remote"]["only_cloud"] == []


@pytest.mark.asyncio
async def test_cloud_status_counts_generic_markdown_assets_inside_skills_dir(tmp_path: Path, monkeypatch) -> None:
    _write_project_binding(tmp_path)
    skills_dir = tmp_path / ".github" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "JavaScript.md").write_text("# Autonomous JavaScript skill\n", encoding="utf-8")

    DummyCloudClient.remote_assets = {
        "skill": [
            {
                "id": "asset-js",
                "asset_type": "skill",
                "path": ".github/skills/JavaScript.md",
                "content": "# Autonomous JavaScript skill\n",
            }
        ],
        "prompt": [],
        "spec": [],
    }
    monkeypatch.setattr(cloud_tools, "CloudClient", DummyCloudClient)
    monkeypatch.setattr(cloud_tools, "detect_environment", lambda: "vscode-copilot")

    result = await cloud_tools._cloud_status(
        {"workspace": str(tmp_path)},
        Settings(token="t", base_url="https://api.example.test"),
    )

    payload = json.loads(result[0].text)
    assert payload["total_local"] == 1
    assert payload["synced_to_cloud"] == 1
    assert payload["pending_push"] == 0
    assert payload["remote"]["only_cloud"] == []


@pytest.mark.asyncio
async def test_cloud_status_writes_sync_state_with_normalized_keys(tmp_path: Path, monkeypatch) -> None:
    _write_project_binding(tmp_path)
    github = tmp_path / ".github"
    (github / "agents").mkdir(parents=True)
    (github / "skills").mkdir(parents=True)
    (github / "copilot-instructions.md").write_text("# Copilot\n", encoding="utf-8")
    (github / "agents" / "ado-devops.agent.md").write_text("# Agent\n", encoding="utf-8")
    (github / "skills" / "azure-security.skill.md").write_text("# Skill\n", encoding="utf-8")

    DummyCloudClient.remote_assets = {
        "skill": [
            {
                "id": "agent-id",
                "asset_type": "skill",
                "path": ".github/agents/ado-devops.agent.md",
                "content": "# Agent\n",
            },
            {
                "id": "skill-id",
                "asset_type": "skill",
                "path": ".github/skills/azure-security.skill.md",
                "content": "# Skill\n",
            },
        ],
        "prompt": [
            {
                "id": "prompt-id",
                "asset_type": "prompt",
                "path": ".github/copilot-instructions.md",
                "content": "# Copilot\n",
            }
        ],
        "spec": [],
    }
    monkeypatch.setattr(cloud_tools, "CloudClient", DummyCloudClient)
    monkeypatch.setattr(cloud_tools, "detect_environment", lambda: "vscode-copilot")

    await cloud_tools._cloud_status(
        {"workspace": str(tmp_path)},
        Settings(token="t", base_url="https://api.example.test"),
    )

    sync_state = json.loads((tmp_path / ".acm" / "sync-state.json").read_text(encoding="utf-8"))
    assert sync_state["stage"] == "status"
    assert sync_state["payload"]["only_cloud"] == []
    assert sync_state["payload"]["only_local"] == []
    assert sync_state["payload"]["synced"] == [
        "agents/ado-devops.agent.md",
        "prompt/copilot-instructions.md",
        "skill/azure-security.skill.md",
    ]


@pytest.mark.asyncio
async def test_cloud_status_uses_copilot_mode_when_environment_is_unknown(tmp_path: Path, monkeypatch) -> None:
    _write_project_binding(tmp_path)
    github = tmp_path / ".github"
    (github / "agents").mkdir(parents=True)
    (github / "copilot-instructions.md").write_text("# Copilot\n", encoding="utf-8")
    (github / "agents" / "ado-devops.agent.md").write_text("# Agent\n", encoding="utf-8")

    DummyCloudClient.remote_assets = {
        "skill": [
            {
                "id": "agent-id",
                "asset_type": "skill",
                "path": ".github/agents/ado-devops.agent.md",
                "content": "# Agent\n",
            }
        ],
        "prompt": [
            {
                "id": "prompt-id",
                "asset_type": "prompt",
                "path": ".github/copilot-instructions.md",
                "content": "# Copilot\n",
            }
        ],
        "spec": [],
    }
    monkeypatch.setattr(cloud_tools, "CloudClient", DummyCloudClient)
    monkeypatch.setattr(cloud_tools, "detect_environment", lambda: "unknown")

    result = await cloud_tools._cloud_status(
        {"workspace": str(tmp_path)},
        Settings(token="t", base_url="https://api.example.test"),
    )

    payload = json.loads(result[0].text)
    assert payload["environment"] == "vscode-copilot"
    assert payload["total_local"] == 2
    assert payload["synced_to_cloud"] == 2

    sync_state = json.loads((tmp_path / ".acm" / "sync-state.json").read_text(encoding="utf-8"))
    assert sync_state["payload"]["only_cloud"] == []
