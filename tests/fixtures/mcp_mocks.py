from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DummyToolCall:
    name: str
    arguments: dict[str, object]
