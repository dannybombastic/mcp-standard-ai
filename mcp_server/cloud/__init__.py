"""Cloud module: cliente HTTP y sincronización con la plataforma central."""

from .client import CloudClient
from .sync import SyncManager

__all__ = ["CloudClient", "SyncManager"]
