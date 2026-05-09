from __future__ import annotations

import json

from mcp_server.storage.registry import REGISTRY_VERSION, RegistryManager


def test_load_initializes_empty_registry_when_file_missing(tmp_path) -> None:
    registry_path = tmp_path / ".ai" / "registry.json"
    manager = RegistryManager(registry_path)

    manager.load()

    assert manager.list_all() == []
    assert manager._data["version"] == REGISTRY_VERSION


def test_upsert_and_get_roundtrip(registry_manager, sample_asset) -> None:
    registry_manager.upsert(sample_asset)

    result = registry_manager.get("skill", "python-best-practices")

    assert result == sample_asset


def test_remove_existing_asset_marks_dirty(registry_manager, sample_asset) -> None:
    registry_manager.upsert(sample_asset)

    removed = registry_manager.remove("skill", "python-best-practices")

    assert removed is True
    assert registry_manager.get("skill", "python-best-practices") is None


def test_search_matches_name_slug_and_tags(registry_manager) -> None:
    registry_manager.upsert(
        {
            "type": "skill",
            "slug": "python-best-practices",
            "name": "Python Best Practices",
            "path": "skills/python-best-practices.md",
            "tags": ["python", "style"],
            "cloud_id": None,
            "cloud_slug": None,
            "synced_at": None,
            "checksum": "abc123",
        }
    )

    by_name = registry_manager.search("best")
    by_slug = registry_manager.search("python-best")
    by_tag = registry_manager.search("style")

    assert len(by_name) == 1
    assert len(by_slug) == 1
    assert len(by_tag) == 1


def test_save_persists_json_to_disk(registry_manager, sample_asset) -> None:
    registry_manager.upsert(sample_asset)
    registry_manager.save()

    payload = json.loads(registry_manager.registry_path.read_text(encoding="utf-8"))

    assert payload["assets"]["skill/python-best-practices"]["slug"] == "python-best-practices"
    assert payload["updated_at"]
