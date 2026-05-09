"""Cliente HTTP asíncrono para la API de la plataforma cloud."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import httpx

from mcp_server.config import Settings

logger = logging.getLogger(__name__)

# Timeouts (segundos)
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 30.0


class CloudAPIError(Exception):
    """Error de la API cloud."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"CloudAPI {status_code}: {message}")


class CloudClient:
    """
    Cliente HTTP para la plataforma AI Context Manager Cloud.

    Todos los métodos son async y usan httpx.AsyncClient.
    Autentica con Token PAT en la cabecera Authorization.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: httpx.AsyncClient | None = None
        self._owned = False  # True si nosotros creamos el cliente (lazy)

    # ------------------------------------------------------------------
    # Ciclo de vida del cliente HTTP
    # ------------------------------------------------------------------

    def _make_httpx_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.settings.base_url,
            headers=self.settings.auth_headers,
            timeout=httpx.Timeout(connect=CONNECT_TIMEOUT, read=READ_TIMEOUT, write=30.0, pool=5.0),
            follow_redirects=True,
        )

    async def __aenter__(self) -> "CloudClient":
        self._client = self._make_httpx_client()
        self._owned = False
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client and not self._owned:
            await self._client.aclose()
            self._client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        """Retorna el cliente HTTP. Lo crea lazy si no hay contexto activo."""
        if self._client is None:
            self._client = self._make_httpx_client()
            self._owned = True
        return self._client

    async def aclose(self) -> None:
        """Cierra el cliente HTTP si fue creado en modo lazy."""
        if self._client and self._owned:
            await self._client.aclose()
            self._client = None
            self._owned = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, **params: Any) -> Any:
        client = self._ensure_client()
        resp = await client.get(path, params=params or None)
        self._raise_for_status(resp)
        return resp.json()

    async def _post(self, path: str, data: dict[str, Any]) -> Any:
        client = self._ensure_client()
        resp = await client.post(path, json=data)
        self._raise_for_status(resp)
        return resp.json()

    async def _patch(self, path: str, data: dict[str, Any]) -> Any:
        client = self._ensure_client()
        resp = await client.patch(path, json=data)
        self._raise_for_status(resp)
        return resp.json()

    async def _delete(self, path: str) -> None:
        client = self._ensure_client()
        resp = await client.delete(path)
        self._raise_for_status(resp)

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.is_error:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise CloudAPIError(resp.status_code, detail)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        """Verifica conectividad con la API. Retorna True si OK.

        Django API actual no expone /health/, así que probamos con /projects/.
        """
        try:
            await self._get("/api/v1/projects/")
            return True
        except Exception as e:
            logger.debug("Ping fallido: %s", e)
            return False

    # ------------------------------------------------------------------
    # Proyectos
    # ------------------------------------------------------------------

    async def get_project(self, slug: str) -> dict[str, Any]:
        """Obtiene un proyecto por slug."""
        return await self._get(f"/api/v1/projects/{slug}/")

    async def ensure_project(self, slug: str) -> None:
        """Falla si el proyecto no existe o no pertenece al usuario."""
        await self.get_project(slug)

    async def list_projects(self) -> list[dict[str, Any]]:
        result = await self._get("/api/v1/projects/")
        return result.get("results", result) if isinstance(result, dict) else result

    # ------------------------------------------------------------------
    # Assets (skills, prompts, specs)
    # ------------------------------------------------------------------

    async def list_assets(self, asset_type: str, project_slug: str | None = None) -> list[dict[str, Any]]:
        """Lista assets filtrando por tipo y opcionalmente por proyecto."""
        params: dict[str, Any] = {"type": asset_type}
        if project_slug:
            params["project"] = project_slug
        result = await self._get("/api/v1/assets/", **params)
        return result.get("results", result) if isinstance(result, dict) else result

    async def get_asset(self, asset_id: str) -> dict[str, Any]:
        """Obtiene un asset por id (UUID en Django)."""
        return await self._get(f"/api/v1/assets/{asset_id}/")

    async def create_asset(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._post("/api/v1/assets/", payload)

    async def update_asset(self, asset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._patch(f"/api/v1/assets/{asset_id}/", payload)

    async def delete_asset(self, asset_id: str) -> None:
        await self._delete(f"/api/v1/assets/{asset_id}/")

    # ------------------------------------------------------------------
    # Push / Pull de contenido markdown (contrato Django)
    # ------------------------------------------------------------------

    async def push_asset_content(
        self,
        local_path: Path,
        asset_type: str,
        project_slug: str,
        asset_path: str,
        name: str,
        cloud_id: str | None = None,
    ) -> dict[str, Any]:
        """Crea o actualiza un Asset en Django."""
        content = local_path.read_text(encoding="utf-8")

        payload: dict[str, Any] = {
            "project": project_slug,
            "asset_type": asset_type,
            "name": name,
            "path": asset_path,
            "content": content,
        }

        if cloud_id:
            return await self.update_asset(cloud_id, payload)
        return await self.create_asset(payload)

    async def pull_asset_content(self, asset_id: str, target_path: Path) -> dict[str, Any]:
        """Descarga un asset de Django y lo escribe en target_path."""
        asset = await self.get_asset(asset_id)
        content = asset.get("content", "")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        return asset

    # ------------------------------------------------------------------
    # PAT (Personal Access Tokens)
    # ------------------------------------------------------------------

    async def list_tokens(self) -> list[dict[str, Any]]:
        result = await self._get("/api/v1/tokens/")
        return result.get("results", result) if isinstance(result, dict) else result

    async def create_token(self, name: str) -> dict[str, Any]:
        """Crea un nuevo PAT. Retorna el token en texto plano (solo en creación)."""
        return await self._post("/api/v1/tokens/", {"name": name})
