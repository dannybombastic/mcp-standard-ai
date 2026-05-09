"""Punto de entrada: python -m mcp_server"""

import asyncio
from mcp_server.server import run


def main() -> None:
    """Entry point para el script instalado (ai-context-manager)."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
