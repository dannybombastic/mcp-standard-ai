from __future__ import annotations

import pytest


@pytest.fixture
def sample_asset() -> dict[str, object]:
    return {
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
