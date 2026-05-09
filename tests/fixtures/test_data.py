from __future__ import annotations


def make_asset(asset_type: str = "skill", slug: str = "sample") -> dict[str, object]:
    return {
        "type": asset_type,
        "slug": slug,
        "name": f"{asset_type}:{slug}",
        "path": f"{asset_type}s/{slug}.md",
        "tags": [asset_type],
        "cloud_id": None,
        "cloud_slug": None,
        "synced_at": None,
        "checksum": "deadbeef",
    }
