from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_server.config import Settings
from mcp_server.resources import asset_resources


class FakeServer:
    def __init__(self) -> None:
        self._list_handler = None
        self._read_handler = None

    def list_resources(self):
        def deco(fn):
            self._list_handler = fn
            return fn

        return deco

    def read_resource(self):
        def deco(fn):
            self._read_handler = fn
            return fn

        return deco


@pytest.mark.asyncio
async def test_register_asset_resources_list_and_read(tmp_path: Path, monkeypatch) -> None:
    ai = tmp_path / ".ai"
    (ai / "skills").mkdir(parents=True)
    (ai / "skills" / "demo.md").write_text("# Demo", encoding="utf-8")
    (ai / "registry.json").write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "now",
                "assets": {
                    "skill/demo": {
                        "type": "skill",
                        "slug": "demo",
                        "name": "Demo",
                        "path": "skills/demo.md",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    server = FakeServer()
    asset_resources.register_asset_resources(server, Settings())

    resources = await server._list_handler()
    assert len(resources) == 1
    assert str(resources[0].uri) == "standarcloud://skill/demo"

    content = await server._read_handler("standarcloud://skill/demo")
    assert content == "# Demo"


@pytest.mark.asyncio
async def test_read_resource_rejects_bad_uri(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = FakeServer()
    asset_resources.register_asset_resources(server, Settings())

    with pytest.raises(ValueError):
        await server._read_handler("http://bad")
