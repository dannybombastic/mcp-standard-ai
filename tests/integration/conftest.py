from __future__ import annotations

import pytest

from mcp_server.cloud.client import CloudClient
from mcp_server.config import Settings


@pytest.fixture
def cloud_settings() -> Settings:
    return Settings(base_url="https://api.example.test", token="secret-token")


@pytest.fixture
def cloud_client(cloud_settings: Settings) -> CloudClient:
    return CloudClient(cloud_settings)
