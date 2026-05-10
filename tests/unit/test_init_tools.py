from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_server.config import Settings
from mcp_server.tools import init_tools


@pytest.mark.asyncio
async def test_ai_status_reports_not_initialized(tmp_path: Path) -> None:
    result = await init_tools._ai_status({"workspace": str(tmp_path)}, Settings())
    payload = json.loads(result[0].text)

    assert payload["initialized"] is False


@pytest.mark.asyncio
async def test_ai_status_reports_counts_for_initialized_workspace(tmp_path: Path) -> None:
    # Manually create .acm structure (what StorageResolver expects)
    acm_dir = tmp_path / ".acm"
    (acm_dir / "skills").mkdir(parents=True, exist_ok=True)
    (acm_dir / "skills" / "a.md").write_text("# s", encoding="utf-8")

    result = await init_tools._ai_status({"workspace": str(tmp_path)}, Settings(token="t", base_url="u"))
    payload = json.loads(result[0].text)

    assert payload["initialized"] is True
    assert payload["asset_counts"]["skills"] == 1
    assert payload["cloud_configured"] is True
