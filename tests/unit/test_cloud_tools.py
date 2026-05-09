from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_server.config import Settings
from mcp_server.tools import cloud_tools


class DummySync:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def push_asset(self, asset_type: str, slug: str):
        self.calls.append(("push_asset", (asset_type, slug)))
        return {"ok": True, "mode": "single"}

    async def push_all(self, dry_run: bool = False):
        self.calls.append(("push_all", dry_run))
        return [{"ok": True, "dry_run": dry_run}]

    async def pull_all(self, dry_run: bool = False):
        self.calls.append(("pull_all", dry_run))
        return [{"ok": True, "dry_run": dry_run}]

    async def status(self):
        self.calls.append(("status", None))
        return {"remote_total": 1}


@pytest.mark.asyncio
async def test_cloud_push_requires_token(tmp_path: Path) -> None:
    result = await cloud_tools._cloud_push({"workspace": str(tmp_path)}, Settings(token="", base_url="x"))

    payload = json.loads(result[0].text)
    assert "error" in payload


@pytest.mark.asyncio
async def test_cloud_sync_uses_make_sync_and_respects_dry_run(tmp_path: Path, monkeypatch) -> None:
    dummy = DummySync()
    monkeypatch.setattr(cloud_tools, "_make_sync", lambda settings, paths, registry: dummy)

    result = await cloud_tools._cloud_sync(
        {"workspace": str(tmp_path), "dry_run": True},
        Settings(token="t", base_url="https://api.example.test"),
    )

    payload = json.loads(result[0].text)
    assert payload["pushed"][0]["dry_run"] is True
    assert payload["pulled"][0]["dry_run"] is True


@pytest.mark.asyncio
async def test_cloud_push_single_asset_route(tmp_path: Path, monkeypatch) -> None:
    dummy = DummySync()
    monkeypatch.setattr(cloud_tools, "_make_sync", lambda settings, paths, registry: dummy)

    result = await cloud_tools._cloud_push(
        {"workspace": str(tmp_path), "type": "skill", "slug": "demo"},
        Settings(token="t", base_url="https://api.example.test"),
    )

    payload = json.loads(result[0].text)
    assert payload[0]["mode"] == "single"
    assert ("push_asset", ("skill", "demo")) in dummy.calls


@pytest.mark.asyncio
async def test_cloud_status_reports_pending_and_synced(tmp_path: Path, monkeypatch) -> None:
    ai = tmp_path / ".ai"
    ai.mkdir(parents=True)
    (ai / "registry.json").write_text(
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
