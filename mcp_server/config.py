"""Configuración del MCP leída desde variables de entorno."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración principal del MCP server."""

    model_config = SettingsConfigDict(
        env_prefix="AI_CONTEXT_MANAGER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Cloud
    base_url: str = ""
    token: str = ""

    # Storage
    storage_mode: str = "workspace"  # workspace | global

    # Logging
    log_level: str = "INFO"

    # Server
    server_name: str = "ai-context-manager"
    server_version: str = "0.1.0"

    @property
    def has_cloud_config(self) -> bool:
        """Retorna True si hay configuración cloud disponible."""
        return bool(self.base_url and self.token)

    @property
    def auth_headers(self) -> dict[str, str]:
        """Headers de autenticación para el cliente HTTP."""
        token = (self.token or "").strip()
        if not token:
            return {}
        # NEVER log the token value
        return {"Authorization": f"Token {token}"}


# Instancia global (singleton)
settings = Settings()
