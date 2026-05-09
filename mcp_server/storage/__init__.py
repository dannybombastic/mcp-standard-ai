"""Storage module: gestión de paths y registry local."""

from .paths import StorageResolver
from .registry import RegistryManager

__all__ = ["StorageResolver", "RegistryManager"]
