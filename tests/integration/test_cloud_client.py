from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from mcp_server.cloud.client import CloudAPIError


@pytest.mark.asyncio
async def test_list_projects_returns_results_list(cloud_client, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://api.example.test/api/v1/projects/",
        json={"results": [{"slug": "demo"}]},
    )

    result = await cloud_client.list_projects()

    assert result == [{"slug": "demo"}]


@pytest.mark.asyncio
async def test_create_token_posts_payload(cloud_client, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.example.test/api/v1/tokens/",
        json={"name": "ci-token", "token": "plain-text"},
    )

    result = await cloud_client.create_token("ci-token")

    assert result["name"] == "ci-token"
    request = httpx_mock.get_requests()[0]
    assert request.headers["Authorization"] == "Token secret-token"


@pytest.mark.asyncio
async def test_get_raises_cloud_api_error_for_401(cloud_client, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://api.example.test/api/v1/projects/private/",
        status_code=401,
        json={"detail": "Unauthorized"},
    )

    with pytest.raises(CloudAPIError) as excinfo:
        await cloud_client.get_project("private")

    assert excinfo.value.status_code == 401
    assert "Unauthorized" in excinfo.value.message


@pytest.mark.asyncio
async def test_ping_returns_false_when_request_fails(cloud_client, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://api.example.test/api/v1/projects/",
        status_code=500,
        json={"detail": "boom"},
    )

    result = await cloud_client.ping()

    assert result is False
