from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_push_asset_content_creates_payload_from_file(cloud_client, tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.md"
    source.write_text("# hello", encoding="utf-8")

    captured: dict[str, object] = {}

    async def _fake_create(payload: dict[str, object]) -> dict[str, object]:
        captured.update(payload)
        return {"id": "a1", **payload}

    monkeypatch.setattr(cloud_client, "create_asset", _fake_create)

    result = await cloud_client.push_asset_content(
        local_path=source,
        asset_type="prompt",
        project_slug="demo",
        asset_path="prompts/sample.md",
        name="sample",
    )

    assert result["id"] == "a1"
    assert captured["content"] == "# hello"
    assert captured["asset_type"] == "prompt"


@pytest.mark.asyncio
async def test_pull_asset_content_writes_markdown_to_target(cloud_client, tmp_path: Path, monkeypatch) -> None:
    async def _fake_get(asset_id: str) -> dict[str, object]:
        return {"id": asset_id, "content": "from-cloud"}

    monkeypatch.setattr(cloud_client, "get_asset", _fake_get)
    target = tmp_path / "skills" / "x.md"

    result = await cloud_client.pull_asset_content("asset-1", target)

    assert result["id"] == "asset-1"
    assert target.read_text(encoding="utf-8") == "from-cloud"
