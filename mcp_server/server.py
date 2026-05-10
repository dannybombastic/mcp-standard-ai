"""Servidor MCP principal para StandarCloud AI Context Manager."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mcp_server.config import settings
from mcp_server.tools.init_tools import _ai_status
from mcp_server.tools.cloud_tools import _CLOUD_TOOLS, _cloud_pull, _cloud_push, _cloud_status, _cloud_sync
from mcp_server.tools.memory_tools import _MEMORY_TOOLS, _memory_add, _memory_list, _memory_materialize_history, _session_ensure
from mcp_server.tools.document_tools import _DOCUMENT_SYNC_TOOLS, handle_detect_environment, handle_materialize_documents, handle_sync_environment_docs
from mcp_server.tools.standard_init_tools import _STANDARD_INIT_TOOLS, _standard_init
from mcp_server.resources.asset_resources import register_asset_resources
from mcp_server.resources.catalog_resources import register_catalog_resources

logger = logging.getLogger(__name__)

ToolHandler = Callable[[dict[str, Any], Any], Awaitable[list[TextContent]]]


def create_server() -> Server:
    """Crea y configura el servidor MCP con todos los tools registrados."""
    server = Server(
        name="standarcloud-ai-context",
        version="0.1.0",
    )

    # Registrar recursos MCP
    register_asset_resources(server, settings)
    register_catalog_resources(server)

    # Registrar todas las tools en un único handler para evitar sobrescrituras
    tools: list[Tool] = [*_STANDARD_INIT_TOOLS, *_DOCUMENT_SYNC_TOOLS]
    handlers: dict[str, ToolHandler] = {
        "ai_status": _ai_status,
        "ai_standard_init": _standard_init,
    }

    # Wrappers para herramientas de documentos
    async def _detect_environment_wrapper(args: dict[str, Any], _settings: Any) -> list[TextContent]:
        return await handle_detect_environment(Path.cwd(), args)

    async def _materialize_documents_wrapper(args: dict[str, Any], _settings: Any) -> list[TextContent]:
        return await handle_materialize_documents(Path.cwd(), args)

    async def _sync_environment_docs_wrapper(args: dict[str, Any], _settings: Any) -> list[TextContent]:
        return await handle_sync_environment_docs(Path.cwd(), args)

    handlers["ai_detect_environment"] = _detect_environment_wrapper
    handlers["ai_materialize_documents"] = _materialize_documents_wrapper
    handlers["ai_sync_environment_docs"] = _sync_environment_docs_wrapper

    if settings.token or settings.base_url:
        tools.extend(_CLOUD_TOOLS)
        tools.extend(_MEMORY_TOOLS)
        handlers.update(
            {
                "ai_cloud_push": _cloud_push,
                "ai_cloud_pull": _cloud_pull,
                "ai_cloud_sync": _cloud_sync,
                "ai_cloud_status": _cloud_status,
                "ai_session_ensure": _session_ensure,
                "ai_memory_add": _memory_add,
                "ai_memory_list": _memory_list,
                "ai_memory_materialize_history": _memory_materialize_history,
            }
        )
        logger.info("Cloud tools activadas (base_url=%s)", settings.base_url)
    else:
        logger.info("Cloud tools desactivadas (AI_CONTEXT_MANAGER_TOKEN no configurado)")

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return tools

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name not in handlers:
            raise ValueError(f"Tool desconocida: {name}")
        return await handlers[name](arguments or {}, settings)

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
