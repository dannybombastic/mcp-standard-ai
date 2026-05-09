from __future__ import annotations

from mcp_server.config import Settings


def test_has_cloud_config_true_when_base_url_and_token_present() -> None:
    settings = Settings(base_url="https://api.example.test", token="secret")

    assert settings.has_cloud_config is True


def test_has_cloud_config_false_when_token_missing() -> None:
    settings = Settings(base_url="https://api.example.test", token="")

    assert settings.has_cloud_config is False


def test_auth_headers_contains_authorization_token() -> None:
    settings = Settings(base_url="https://api.example.test", token="secret")

    assert settings.auth_headers == {"Authorization": "Token secret"}


def test_auth_headers_empty_when_token_blank() -> None:
    settings = Settings(base_url="https://api.example.test", token="   ")

    assert settings.auth_headers == {}
