from __future__ import annotations


def assert_iso8601(value: str) -> None:
    # Basic invariant: timestamps are non-empty ISO strings with timezone separator.
    assert "T" in value
    assert value.endswith("+00:00") or value.endswith("Z")
