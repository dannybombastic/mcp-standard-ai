from __future__ import annotations


def projects_results_payload(slug: str = "demo") -> dict[str, list[dict[str, str]]]:
    return {"results": [{"slug": slug}]}


def error_payload(detail: str) -> dict[str, str]:
    return {"detail": detail}
