from __future__ import annotations

import mcp_server.__main__ as main_module


def test_main_calls_asyncio_run_with_server_run(monkeypatch) -> None:
    called = {}

    async def fake_run():
        return None

    def fake_asyncio_run(coro):
        called["is_coro"] = hasattr(coro, "__await__")
        coro.close()

    monkeypatch.setattr(main_module, "run", fake_run)
    monkeypatch.setattr(main_module.asyncio, "run", fake_asyncio_run)

    main_module.main()

    assert called["is_coro"] is True
