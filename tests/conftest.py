from __future__ import annotations

import pytest

from mcp_server.config import Settings
from mcp_server.storage.registry import RegistryManager


@pytest.fixture
def test_settings() -> Settings:
    return Settings(base_url="https://api.example.test", token="secret-token")


@pytest.fixture
def registry_manager(tmp_path):
    registry_path = tmp_path / ".ai" / "registry.json"
    manager = RegistryManager(registry_path)
    manager.load()
    return manager
