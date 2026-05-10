from __future__ import annotations

import mcp_server.server as server_module


class DummyServer:
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version


def test_create_server_returns_server_instance() -> None:
    server = server_module.create_server()
    assert server.name == "standarcloud-ai-context"
    assert server.version == "0.1.0"
