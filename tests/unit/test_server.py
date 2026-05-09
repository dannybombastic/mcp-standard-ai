from __future__ import annotations

import mcp_server.server as server_module


class DummyServer:
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version


def test_create_server_registers_tool_groups(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(server_module, "Server", DummyServer)
    monkeypatch.setattr(server_module, "register_asset_resources", lambda server, settings: calls.append("resources"))
    monkeypatch.setattr(server_module, "register_init_tools", lambda server, settings: calls.append("init"))
    monkeypatch.setattr(server_module, "register_asset_tools", lambda server, settings: calls.append("asset"))
    monkeypatch.setattr(server_module, "register_bootstrap_tools", lambda server, settings: calls.append("bootstrap"))
    monkeypatch.setattr(server_module, "register_cloud_tools", lambda server, settings: calls.append("cloud"))
    monkeypatch.setattr(server_module.settings, "token", "")
    monkeypatch.setattr(server_module.settings, "base_url", "")

    server = server_module.create_server()

    assert isinstance(server, DummyServer)
    assert calls == ["resources", "init", "asset", "bootstrap"]


def test_create_server_enables_cloud_tools_when_config_present(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(server_module, "Server", DummyServer)
    monkeypatch.setattr(server_module, "register_asset_resources", lambda server, settings: None)
    monkeypatch.setattr(server_module, "register_init_tools", lambda server, settings: None)
    monkeypatch.setattr(server_module, "register_asset_tools", lambda server, settings: None)
    monkeypatch.setattr(server_module, "register_bootstrap_tools", lambda server, settings: None)
    monkeypatch.setattr(server_module, "register_cloud_tools", lambda server, settings: calls.append("cloud"))
    monkeypatch.setattr(server_module.settings, "token", "x")
    monkeypatch.setattr(server_module.settings, "base_url", "https://api.example.test")

    server_module.create_server()

    assert calls == ["cloud"]
