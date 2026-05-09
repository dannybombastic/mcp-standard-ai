from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_server.storage.paths import AI_DIR, POINTER_FILE, StorageResolver


def test_resolve_workspace_mode_returns_local_ai_dir(tmp_path: Path) -> None:
    resolver = StorageResolver(tmp_path)

    ai_dir = resolver.resolve_ai_dir(mode="workspace")

    assert ai_dir == tmp_path / AI_DIR


def test_resolve_global_mode_requires_project_key(tmp_path: Path) -> None:
    resolver = StorageResolver(tmp_path)

    with pytest.raises(ValueError):
        resolver.resolve_ai_dir(mode="global")


def test_resolve_ai_dir_follows_pointer_when_target_exists(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    pointed = tmp_path / "global" / AI_DIR
    pointed.mkdir(parents=True)

    pointer_file = workspace / AI_DIR / POINTER_FILE
    pointer_file.parent.mkdir(parents=True)
    pointer_file.write_text(json.dumps({"path": str(pointed)}), encoding="utf-8")

    resolver = StorageResolver(workspace)

    assert resolver.resolve_ai_dir() == pointed


def test_get_paths_create_all_creates_standard_directories(tmp_path: Path) -> None:
    resolver = StorageResolver(tmp_path)
    paths = resolver.get_paths()

    paths.create_all()

    assert paths.ai_dir.exists()
    assert paths.context.exists()
    assert paths.skills.exists()
    assert paths.prompts.exists()
    assert paths.specs.exists()
    assert paths.templates.exists()
    assert paths.sync.exists()


def test_asset_dir_raises_for_unknown_type(tmp_path: Path) -> None:
    resolver = StorageResolver(tmp_path)
    paths = resolver.get_paths()

    with pytest.raises(ValueError):
        paths.asset_dir("unknown")


def test_write_pointer_creates_pointer_json(tmp_path: Path) -> None:
    resolver = StorageResolver(tmp_path)
    target = tmp_path / "global" / AI_DIR
    target.mkdir(parents=True)

    resolver.write_pointer(target)

    pointer_file = tmp_path / AI_DIR / POINTER_FILE
    payload = json.loads(pointer_file.read_text(encoding="utf-8"))
    assert payload["path"] == str(target)
    assert payload["mode"] == "global"
