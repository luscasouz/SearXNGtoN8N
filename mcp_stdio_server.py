#!/usr/bin/env python3
"""
MCP SearXNG Server - Stdio Transport
Wrapper para usar o servidor MCP via stdin/stdout (Content-Length framing).
Compatível com Claude Desktop e outros clientes MCP que usam stdio.
"""

import asyncio
import json
import logging
import sys

from mcp_http_sse_server import MCPSearXNGServer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # Logs vão para stderr, stdout é para MCP
)
logger = logging.getLogger('mcp-searxng-stdio')


async def read_message(reader) -> dict | None:
    """Lê uma mensagem JSON-RPC via Content-Length framing."""
    headers = {}
    while True:
        line = await reader.readline()
        if not line:
            return None
        line = line.decode('utf-8').strip()
        if not line:
            break
        if ':' in line:
            key, value = line.split(':', 1)
            headers[key.strip().lower()] = value.strip()

    content_length = int(headers.get('content-length', 0))
    if content_length == 0:
        return None

    data = await reader.readexactly(content_length)
    return json.loads(data.decode('utf-8'))


def write_message(message: dict):
    """Escreve uma mensagem JSON-RPC via Content-Length framing."""
    data = json.dumps(message, ensure_ascii=False)
    encoded = data.encode('utf-8')
    sys.stdout.buffer.write(f"Content-Length: {len(encoded)}\r\n\r\n".encode('utf-8'))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


async def main():
    server = MCPSearXNGServer()
    await server.start_session()

    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    logger.info("MCP SearXNG Stdio Server iniciado")

    try:
        while True:
            message = await read_message(reader)
            if message is None:
                break
            response = await server.handle_jsonrpc(message)
            write_message(response)
    except Exception as e:
        logger.exception(f"Erro no stdio server: {e}")
    finally:
        await server.close_session()
        logger.info("MCP SearXNG Stdio Server encerrado")


if __name__ == '__main__':
    asyncio.run(main())
