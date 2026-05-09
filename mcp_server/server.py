"""Servidor MCP principal para StandarCloud AI Context Manager."""

from __future__ import annotations

import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server

from mcp_server.config import settings
from mcp_server.tools.init_tools import register_init_tools
from mcp_server.tools.asset_tools import register_asset_tools
from mcp_server.tools.bootstrap_tools import register_bootstrap_tools
from mcp_server.tools.cloud_tools import register_cloud_tools
from mcp_server.resources.asset_resources import register_asset_resources

logger = logging.getLogger(__name__)


def create_server() -> Server:
    """Crea y configura el servidor MCP con todos los tools registrados."""
    server = Server(
        name="standarcloud-ai-context",
        version="0.1.0",
    )

    # Registrar recursos MCP
    register_asset_resources(server, settings)

    # Registrar grupos de herramientas
    register_init_tools(server, settings)
    register_asset_tools(server, settings)
    register_bootstrap_tools(server, settings)

    if settings.token or settings.base_url:
        register_cloud_tools(server, settings)
        logger.info("Cloud tools activadas (base_url=%s)", settings.base_url)
    else:
        logger.info("Cloud tools desactivadas (AI_CONTEXT_MANAGER_TOKEN no configurado)")

    return server


async def run() -> None:
    """Arranca el servidor MCP sobre stdio."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    server = create_server()
    logger.info("Iniciando StandarCloud MCP server...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
