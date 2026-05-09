from __future__ import annotations

from pathlib import Path

import pytest

from mcp_server.cloud.sync import SyncManager, _extract_name, _extract_tags
from mcp_server.storage.paths import StorageResolver
from mcp_server.storage.registry import RegistryManager


class FakeClient:
    def __init__(self) -> None:
        self.assets_by_type: dict[str, list[dict[str, object]]] = {"skill": [], "prompt": [], "spec": []}

    async def ensure_project(self, project_slug: str) -> None:
        return None

    async def push_asset_content(self, **kwargs):
        return {"id": "cloud-1", "updated_at": "now"}

    async def list_assets(self, asset_type: str, project_slug: str | None = None):
        return self.assets_by_type.get(asset_type, [])

    async def pull_asset_content(self, asset_id: str, target_path: Path):
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text("pulled", encoding="utf-8")
        return {"id": asset_id, "name": "Pulled", "updated_at": "now"}


def _make_manager(tmp_path: Path) -> tuple[SyncManager, RegistryManager, FakeClient]:
    resolver = StorageResolver(tmp_path)
    paths = resolver.get_paths()
    paths.create_all()
    registry = RegistryManager(paths.registry)
    registry.load()
    client = FakeClient()
    return SyncManager(paths=paths, registry=registry, client=client), registry, client


@pytest.mark.asyncio
async def test_push_all_dry_run_reports_create(tmp_path: Path) -> None:
    manager, _, _ = _make_manager(tmp_path)
    (tmp_path / ".ai" / "skills" / "demo.md").write_text("# Demo", encoding="utf-8")

    result = await manager.push_all(project_slug="project-a", dry_run=True)

    assert result[0]["action"] == "create"
    assert result[0]["status"] == "dry_run"


@pytest.mark.asyncio
async def test_push_all_skips_when_checksum_unchanged_and_cloud_id_exists(tmp_path: Path) -> None:
    manager, registry, _ = _make_manager(tmp_path)
    md = tmp_path / ".ai" / "skills" / "same.md"
    md.write_text("content", encoding="utf-8")

    import hashlib

    checksum = hashlib.sha256("content".encode()).hexdigest()
    registry.upsert(
        {
            "type": "skill",
            "slug": "same",
            "name": "Same",
            "path": "skills/same.md",
            "tags": [],
            "cloud_id": "cloud-9",
            "cloud_slug": None,
            "synced_at": None,
            "checksum": checksum,
        }
    )
    registry.save_if_dirty()

    result = await manager.push_all(project_slug="project-a")

    assert result[0]["action"] == "skip"
    assert result[0]["status"] == "no_changes"


@pytest.mark.asyncio
async def test_push_asset_returns_error_status_when_project_slug_missing(tmp_path: Path) -> None:
    manager, _, _ = _make_manager(tmp_path)
    (tmp_path / ".ai" / "skills" / "need-project.md").write_text("body", encoding="utf-8")

    result = await manager.push_asset("skill", "need-project")

    assert result["action"] == "error"
    assert "project_slug" in result["status"]


@pytest.mark.asyncio
async def test_pull_all_dry_run_reports_create(tmp_path: Path) -> None:
    manager, _, client = _make_manager(tmp_path)
    client.assets_by_type["skill"] = [{"id": "c1", "path": "skills/new-skill.md", "content_hash": "h1"}]

    result = await manager.pull_all(dry_run=True)

    assert result[0]["action"] == "create"
    assert result[0]["status"] == "dry_run"


@pytest.mark.asyncio
async def test_pull_all_writes_file_and_updates_registry(tmp_path: Path) -> None:
    manager, registry, client = _make_manager(tmp_path)
    client.assets_by_type["skill"] = [{"id": "c1", "path": "skills/new-skill.md", "content_hash": "x"}]

    result = await manager.pull_all(dry_run=False)

    assert result[0]["status"] == "ok"
    assert (tmp_path / ".ai" / "skills" / "new-skill.md").exists()
    registry.load()
    assert registry.get("skill", "new-skill") is not None


@pytest.mark.asyncio
async def test_status_reports_only_local_only_cloud_and_synced(tmp_path: Path) -> None:
    manager, registry, client = _make_manager(tmp_path)
    registry.upsert(
        {
            "type": "skill",
            "slug": "local",
            "name": "Local",
            "path": "skills/local.md",
            "tags": [],
            "cloud_id": None,
            "cloud_slug": None,
            "synced_at": None,
            "checksum": "1",
        }
    )
    registry.upsert(
        {
            "type": "skill",
            "slug": "shared",
            "name": "Shared",
            "path": "skills/shared.md",
            "tags": [],
            "cloud_id": "c",
            "cloud_slug": None,
            "synced_at": None,
            "checksum": "2",
        }
    )
    registry.save_if_dirty()

    client.assets_by_type["skill"] = [
        {"id": "ca", "path": "skills/shared.md"},
        {"id": "cb", "path": "skills/remote.md"},
    ]

    status = await manager.status()

    assert "skill/shared" in status["synced"]
    assert "skill/local" in status["only_local"]
    assert "skill/remote" in status["only_cloud"]


def test_extract_name_and_tags_helpers() -> None:
    content = "---\nname: Demo\ntags: [a, 'b', \"c\"]\n---\nBody"

    assert _extract_name(content) == "Demo"
    assert _extract_tags(content) == ["a", "b", "c"]
    assert _extract_name("no front matter") is None
    assert _extract_tags("no front matter") == []
