"""Resolución de rutas de storage: workspace-local vs global por usuario."""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path


AI_DIR = ".ai"
POINTER_FILE = ".pointer.json"
SYNC_DIR = ".sync"
CONTEXT_DIR = "context"
SKILLS_DIR = "skills"
PROMPTS_DIR = "prompts"
SPECS_DIR = "specs"
TEMPLATES_DIR = "templates"


def _global_ai_root() -> Path:
    """Retorna la raíz del storage global según el SO."""
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "ai"
        return Path.home() / ".ai"
    return Path.home() / ".ai"


class StorageResolver:
    """
    Resuelve qué directorio `.ai/` usar para un workspace dado.

    Modos:
    - workspace: `./<workspace>/.ai/`
    - global: `~/.ai/projects/<project_key>/` (o APPDATA en Windows)

    Si hay un `.ai/.pointer.json` en el workspace, redirige al path global real.
    """

    def __init__(self, workspace: Path | str | None = None):
        self.workspace = Path(workspace).resolve() if workspace else Path.cwd()

    # ------------------------------------------------------------------
    # Resolución del directorio .ai/
    # ------------------------------------------------------------------

    def resolve_ai_dir(self, mode: str = "workspace", project_key: str | None = None) -> Path:
        """
        Retorna el path real del directorio .ai/ a usar.

        Si existe un .pointer.json en el workspace, sigue el puntero (modo global).
        """
        workspace_ai = self.workspace / AI_DIR
        pointer_file = workspace_ai / POINTER_FILE

        # Si hay puntero, seguirlo
        if pointer_file.exists():
            try:
                data = json.loads(pointer_file.read_text(encoding="utf-8"))
                pointed = Path(data.get("path", ""))
                if pointed.exists():
                    return pointed
            except (json.JSONDecodeError, KeyError):
                pass

        if mode == "global":
            if not project_key:
                raise ValueError("project_key es requerido para modo global")
            return _global_ai_root() / "projects" / project_key / AI_DIR

        # Por defecto: workspace
        return workspace_ai

    # ------------------------------------------------------------------
    # Subdirectorios estándar
    # ------------------------------------------------------------------

    def get_paths(self, mode: str = "workspace", project_key: str | None = None) -> "AIPaths":
        """Retorna un objeto con todos los subdirectorios del .ai/."""
        ai_dir = self.resolve_ai_dir(mode=mode, project_key=project_key)
        return AIPaths(ai_dir)

    # ------------------------------------------------------------------
    # Escritura del puntero (modo global)
    # ------------------------------------------------------------------

    def write_pointer(self, global_ai_path: Path) -> None:
        """
        Escribe `.ai/.pointer.json` en el workspace apuntando al path global.
        Solo se usa cuando storageMode=global.
        """
        workspace_ai = self.workspace / AI_DIR
        workspace_ai.mkdir(parents=True, exist_ok=True)
        pointer = workspace_ai / POINTER_FILE
        pointer.write_text(
            json.dumps({"path": str(global_ai_path), "mode": "global"}, indent=2),
            encoding="utf-8",
        )


class AIPaths:
    """Contenedor con todos los paths estándar de una carpeta .ai/."""

    def __init__(self, ai_dir: Path):
        self.ai_dir = ai_dir
        self.registry = ai_dir / "registry.json"
        self.context = ai_dir / CONTEXT_DIR
        self.skills = ai_dir / SKILLS_DIR
        self.prompts = ai_dir / PROMPTS_DIR
        self.specs = ai_dir / SPECS_DIR
        self.templates = ai_dir / TEMPLATES_DIR
        self.sync = ai_dir / SYNC_DIR
        self.sync_state = self.sync / "state.json"
        self.sync_project = self.sync / "project.json"
        self.bootstrap = self.context / "MODEL_BOOTSTRAP.md"
        self.guidelines = self.context / "AI_GUIDELINES.md"

    def create_all(self) -> None:
        """Crea todos los directorios necesarios."""
        for d in [
            self.ai_dir,
            self.context,
            self.skills,
            self.prompts,
            self.specs,
            self.templates,
            self.sync,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def subdirs(self) -> list[Path]:
        return [self.context, self.skills, self.prompts, self.specs, self.templates, self.sync]

    def asset_dir(self, asset_type: str) -> Path:
        """Retorna el directorio para un tipo de asset dado."""
        mapping = {
            "skill": self.skills,
            "skills": self.skills,
            "prompt": self.prompts,
            "prompts": self.prompts,
            "spec": self.specs,
            "specs": self.specs,
            "context": self.context,
        }
        if asset_type not in mapping:
            raise ValueError(f"Tipo de asset desconocido: {asset_type}")
        return mapping[asset_type]
