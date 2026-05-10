"""Clase base para adaptadores de entorno."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class AdapterBase(ABC):
    """Base para adaptadores que materializan documentos nativos."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    @abstractmethod
    async def materialize_documents(self, documents: dict[str, Any]) -> dict[str, str]:
        """
        Materializar documentos en ubicaciones nativas del entorno.
        
        Args:
            documents: Dict con documento_id -> contenido
        
        Returns:
            Dict con ruta_materializada -> estado ("created" | "updated" | "skipped")
        """
        pass

    @abstractmethod
    async def import_native_documents(self) -> dict[str, str]:
        """
        Importar documentos nativos del workspace.
        
        Returns:
            Dict con tipo -> contenido leído
        """
        pass

    def _ensure_parent_dir(self, path: Path) -> Path:
        """Asegurar que el directorio padre existe."""
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
