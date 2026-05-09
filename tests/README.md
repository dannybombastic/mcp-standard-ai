# Test Suite

This project uses pytest with async and HTTP mocking support.

## Layout

- `tests/unit/`: fast isolated tests for pure logic and local I/O.
- `tests/integration/`: async workflow tests using mocked HTTP APIs.
- `tests/fixtures/`: reusable builders and helpers.

## Run

```bash
python3 -m pytest tests -q
python3 -m pytest tests/unit -q
python3 -m pytest tests --cov=mcp_server --cov-report=term-missing
```

## Patterns

- Prefer function-style tests with explicit fixtures.
- For async code, use `@pytest.mark.asyncio`.
- For API behavior, use `pytest-httpx` and assert both payload and headers.
- Keep fixtures deterministic and avoid shared mutable state.
