"""State técnico local en `.acm/`."""

from __future__ import annotations

from pathlib import Path


class AcmPaths:
    """Contenedor de estado técnico local en `.acm/`."""

    def __init__(self, workspace: Path | str):
        self.workspace = Path(workspace).resolve()
        self.acm_dir = self.workspace / ".acm"
        self.project = self.acm_dir / "project.json"
        self.sync_state = self.acm_dir / "sync-state.json"
        self.route_cache = self.acm_dir / "route-cache.json"
        self.manifest = self.acm_dir / "manifest.json"

    def create_all(self) -> None:
        self.acm_dir.mkdir(parents=True, exist_ok=True)
