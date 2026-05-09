from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_server.config import Settings
from mcp_server.tools import asset_tools


@pytest.mark.asyncio
async def test_create_get_update_delete_asset_lifecycle(tmp_path: Path) -> None:
    create = await asset_tools._create_asset(
        {
            "workspace": str(tmp_path),
            "type": "skill",
            "slug": "Python Best Practices",
            "name": "Python Best Practices",
            "content": "Body",
            "tags": ["python", "style"],
        },
        Settings(),
    )
    created = json.loads(create[0].text)
    assert created["created"] is True
    assert created["slug"] == "python-best-practices"

    get_result = await asset_tools._get_asset(
        {"workspace": str(tmp_path), "type": "skill", "slug": "python-best-practices"},
        Settings(),
    )
    assert "type: skill" in get_result[0].text
    assert "Body" in get_result[0].text

    update = await asset_tools._update_asset(
        {
            "workspace": str(tmp_path),
            "type": "skill",
            "slug": "python-best-practices",
            "content": "New body",
        },
        Settings(),
    )
    assert json.loads(update[0].text)["updated"] is True

    delete = await asset_tools._delete_asset(
        {"workspace": str(tmp_path), "type": "skill", "slug": "python-best-practices"},
        Settings(),
    )
    assert json.loads(delete[0].text)["deleted"] is True


@pytest.mark.asyncio
async def test_list_assets_filters_by_type_and_tags(tmp_path: Path) -> None:
    await asset_tools._create_asset(
        {
            "workspace": str(tmp_path),
            "type": "skill",
            "slug": "s1",
            "name": "S1",
            "content": "one",
            "tags": ["python"],
        },
        Settings(),
    )
    await asset_tools._create_asset(
        {
            "workspace": str(tmp_path),
            "type": "prompt",
            "slug": "p1",
            "name": "P1",
            "content": "two",
            "tags": ["review"],
        },
        Settings(),
    )

    result_all = await asset_tools._list_assets({"workspace": str(tmp_path), "type": "all"}, Settings())
    all_assets = json.loads(result_all[0].text)
    assert len(all_assets) == 2

    result_tag = await asset_tools._list_assets(
        {"workspace": str(tmp_path), "type": "all", "tags": ["python"]},
        Settings(),
    )
    tag_assets = json.loads(result_tag[0].text)
    assert len(tag_assets) == 1
    assert tag_assets[0]["slug"] == "s1"


def test_asset_tool_helpers() -> None:
    assert asset_tools._to_slug("  Hello World!  ") == "hello-world"

    md = asset_tools._build_markdown("Name", "skill", ["x", "y"], "Body")
    assert md.startswith("---")
    assert "tags: [\"x\", \"y\"]" in md

    assert asset_tools._extract_front_matter_field(md, "name") == "Name"
    assert asset_tools._extract_front_matter_tags(md) == ["x", "y"]
    assert asset_tools._strip_front_matter(md) == "Body"
