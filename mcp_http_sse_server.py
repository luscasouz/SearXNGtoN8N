#!/usr/bin/env python3
"""
MCP SearXNG Server - HTTP/SSE Transport
Servidor MCP para busca na web via SearXNG.
Suporta transporte HTTP/SSE (compatível com n8n, Claude Desktop, etc).
"""

import argparse
import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime

import aiohttp
import aiohttp_cors
from aiohttp import web, ClientTimeout

from config import Config

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mcp-searxng')

# ---------------------------------------------------------------------------
# Tool Definitions
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "web_search",
        "description": (
            "Realiza uma busca geral na web usando SearXNG (metabuscador que agrega "
            "resultados de Google, Bing, DuckDuckGo, Brave, etc). "
            "Retorna títulos, URLs, snippets e engines de origem."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Termo de busca"
                },
                "categories": {
                    "type": "string",
                    "description": "Categorias separadas por vírgula (ex: general, it, science, social media). Padrão: general",
                    "default": "general"
                },
                "engines": {
                    "type": "string",
                    "description": "Engines específicas separadas por vírgula (ex: google,bing,duckduckgo). Opcional."
                },
                "language": {
                    "type": "string",
                    "description": "Código do idioma (ex: pt-BR, en, es). Padrão: pt-BR",
                    "default": "pt-BR"
                },
                "time_range": {
                    "type": "string",
                    "description": "Filtro temporal: day, month, year. Opcional.",
                    "enum": ["day", "month", "year"]
                },
                "pageno": {
                    "type": "integer",
                    "description": "Número da página de resultados. Padrão: 1",
                    "default": 1
                },
                "safesearch": {
                    "type": "integer",
                    "description": "Nível de SafeSearch: 0 (desligado), 1 (moderado), 2 (estrito). Padrão: 0",
                    "enum": [0, 1, 2],
                    "default": 0
                },
                "max_results": {
                    "type": "integer",
                    "description": "Número máximo de resultados a retornar. Padrão: 10",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "news_search",
        "description": (
            "Busca notícias recentes na web via SearXNG. "
            "Atalho para busca na categoria 'news'. "
            "Retorna títulos, URLs, datas e fontes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Termo de busca para notícias"
                },
                "language": {
                    "type": "string",
                    "description": "Código do idioma (ex: pt-BR, en). Padrão: pt-BR",
                    "default": "pt-BR"
                },
                "time_range": {
                    "type": "string",
                    "description": "Filtro temporal: day, month, year. Opcional.",
                    "enum": ["day", "month", "year"]
                },
                "pageno": {
                    "type": "integer",
                    "description": "Página de resultados. Padrão: 1",
                    "default": 1
                },
                "max_results": {
                    "type": "integer",
                    "description": "Máximo de resultados. Padrão: 10",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "images_search",
        "description": (
            "Busca imagens na web via SearXNG. "
            "Retorna URLs das imagens, thumbnails, títulos e fontes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Termo de busca para imagens"
                },
                "engines": {
                    "type": "string",
                    "description": "Engines específicas (ex: google images, bing images). Opcional."
                },
                "language": {
                    "type": "string",
                    "description": "Código do idioma. Padrão: pt-BR",
                    "default": "pt-BR"
                },
                "safesearch": {
                    "type": "integer",
                    "description": "SafeSearch: 0, 1, 2. Padrão: 1",
                    "enum": [0, 1, 2],
                    "default": 1
                },
                "pageno": {
                    "type": "integer",
                    "description": "Página de resultados. Padrão: 1",
                    "default": 1
                },
                "max_results": {
                    "type": "integer",
                    "description": "Máximo de resultados. Padrão: 10",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_page_content",
        "description": (
            "Busca o conteúdo de uma URL e retorna como texto Markdown limpo. "
            "Útil para ler o conteúdo de páginas encontradas nas buscas. "
            "Remove scripts, estilos e elementos desnecessários."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL da página a ser lida"
                },
                "max_length": {
                    "type": "integer",
                    "description": "Tamanho máximo do conteúdo em caracteres. Padrão: 20000",
                    "default": 20000
                }
            },
            "required": ["url"]
        }
    }
]


# ---------------------------------------------------------------------------
# MCPSearXNGServer
# ---------------------------------------------------------------------------
class MCPSearXNGServer:
    """Servidor MCP que expõe ferramentas de busca via SearXNG."""

    def __init__(self):
        self.config = Config
        self.session: aiohttp.ClientSession | None = None
        self.server_info = {
            "name": Config.MCP_SERVER_NAME,
            "version": Config.MCP_SERVER_VERSION
        }
        self.capabilities = {
            "tools": {}
        }
        # SSE sessions: session_id -> asyncio.Queue
        self._sse_sessions: dict[str, asyncio.Queue] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start_session(self):
        """Inicializa a sessão HTTP."""
        timeout = ClientTimeout(total=Config.REQUEST_TIMEOUT)
        self.session = aiohttp.ClientSession(timeout=timeout)
        logger.info(f"Sessão HTTP iniciada. SearXNG URL: {Config.SEARXNG_URL}")

    async def close_session(self):
        """Fecha a sessão HTTP."""
        if self.session:
            await self.session.close()
            logger.info("Sessão HTTP encerrada.")

    # ------------------------------------------------------------------
    # SearXNG API
    # ------------------------------------------------------------------
    async def _searxng_search(self, params: dict) -> dict:
        """Executa busca no SearXNG e retorna JSON."""
        params['format'] = 'json'
        url = f"{Config.SEARXNG_URL}/search"
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return {"error": f"SearXNG retornou status {resp.status}: {text}"}
                return await resp.json()
        except asyncio.TimeoutError:
            return {"error": "Timeout ao conectar com SearXNG"}
        except Exception as e:
            return {"error": f"Erro ao conectar com SearXNG: {str(e)}"}

    async def _fetch_url(self, url: str, max_length: int = 20000) -> str:
        """Busca conteúdo de uma URL e converte para Markdown."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; MCP-SearXNG/1.0)'
            }
            async with self.session.get(url, headers=headers, allow_redirects=True) as resp:
                if resp.status != 200:
                    return f"Erro ao acessar URL: status {resp.status}"
                content_type = resp.headers.get('Content-Type', '')
                if 'text/html' not in content_type and 'text/plain' not in content_type:
                    return f"Tipo de conteúdo não suportado: {content_type}"
                html = await resp.text()
        except asyncio.TimeoutError:
            return "Timeout ao acessar a URL"
        except Exception as e:
            return f"Erro ao acessar URL: {str(e)}"

        try:
            from bs4 import BeautifulSoup
            import html2text

            soup = BeautifulSoup(html, 'html.parser')
            # Remove elementos desnecessários
            for tag in soup(['script', 'style', 'nav', 'footer', 'header',
                             'aside', 'iframe', 'noscript']):
                tag.decompose()

            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.ignore_emphasis = False
            h.body_width = 0  # sem word wrap
            markdown = h.handle(str(soup))

            # Truncar se necessário
            if len(markdown) > max_length:
                markdown = markdown[:max_length] + "\n\n... (conteúdo truncado)"

            return markdown.strip()
        except Exception as e:
            return f"Erro ao processar HTML: {str(e)}"

    # ------------------------------------------------------------------
    # Tool Execution
    # ------------------------------------------------------------------
    async def execute_tool(self, name: str, arguments: dict) -> dict:
        """Executa uma tool MCP e retorna o resultado."""
        logger.info(f"Executando tool: {name} | args: {json.dumps(arguments, ensure_ascii=False)}")

        try:
            if name == "web_search":
                return await self._tool_web_search(arguments)
            elif name == "news_search":
                return await self._tool_news_search(arguments)
            elif name == "images_search":
                return await self._tool_images_search(arguments)
            elif name == "fetch_page_content":
                return await self._tool_fetch_page(arguments)
            else:
                return self._error_response(f"Tool desconhecida: {name}")
        except Exception as e:
            logger.exception(f"Erro ao executar tool {name}")
            return self._error_response(str(e))

    async def _tool_web_search(self, args: dict) -> dict:
        query = args.get('query', '')
        if not query:
            return self._error_response("Parâmetro 'query' é obrigatório")

        params = {'q': query}
        if args.get('categories'):
            params['categories'] = args['categories']
        else:
            params['categories'] = 'general'
        if args.get('engines'):
            params['engines'] = args['engines']
        if args.get('language'):
            params['language'] = args['language']
        if args.get('time_range'):
            params['time_range'] = args['time_range']
        if args.get('pageno'):
            params['pageno'] = args['pageno']
        if args.get('safesearch') is not None:
            params['safesearch'] = args['safesearch']

        max_results = args.get('max_results', Config.DEFAULT_MAX_RESULTS)
        data = await self._searxng_search(params)

        if 'error' in data:
            return self._error_response(data['error'])

        return self._format_search_results(data, max_results, query)

    async def _tool_news_search(self, args: dict) -> dict:
        query = args.get('query', '')
        if not query:
            return self._error_response("Parâmetro 'query' é obrigatório")

        params = {
            'q': query,
            'categories': 'news'
        }
        if args.get('language'):
            params['language'] = args['language']
        if args.get('time_range'):
            params['time_range'] = args['time_range']
        if args.get('pageno'):
            params['pageno'] = args['pageno']

        max_results = args.get('max_results', Config.DEFAULT_MAX_RESULTS)
        data = await self._searxng_search(params)

        if 'error' in data:
            return self._error_response(data['error'])

        return self._format_search_results(data, max_results, query, is_news=True)

    async def _tool_images_search(self, args: dict) -> dict:
        query = args.get('query', '')
        if not query:
            return self._error_response("Parâmetro 'query' é obrigatório")

        params = {
            'q': query,
            'categories': 'images'
        }
        if args.get('engines'):
            params['engines'] = args['engines']
        if args.get('language'):
            params['language'] = args['language']
        if args.get('safesearch') is not None:
            params['safesearch'] = args['safesearch']
        if args.get('pageno'):
            params['pageno'] = args['pageno']

        max_results = args.get('max_results', Config.DEFAULT_MAX_RESULTS)
        data = await self._searxng_search(params)

        if 'error' in data:
            return self._error_response(data['error'])

        return self._format_image_results(data, max_results, query)

    async def _tool_fetch_page(self, args: dict) -> dict:
        url = args.get('url', '')
        if not url:
            return self._error_response("Parâmetro 'url' é obrigatório")

        max_length = args.get('max_length', 20000)
        content = await self._fetch_url(url, max_length)

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"## Conteúdo de: {url}\n\n{content}"
                }
            ],
            "isError": False
        }

    # ------------------------------------------------------------------
    # Formatters
    # ------------------------------------------------------------------
    def _format_search_results(self, data: dict, max_results: int, query: str, is_news: bool = False) -> dict:
        results = data.get('results', [])[:max_results]
        suggestions = data.get('suggestions', [])
        answers = data.get('answers', [])
        total = data.get('number_of_results', 0)

        tipo = "notícias" if is_news else "web"
        lines = [f"## Resultados de busca ({tipo}): \"{query}\"\n"]

        if total:
            lines.append(f"*Aproximadamente {total:,} resultados encontrados*\n")

        # Respostas diretas
        if answers:
            lines.append("### Respostas diretas\n")
            for ans in answers:
                lines.append(f"> {ans}\n")

        # Resultados
        if not results:
            lines.append("Nenhum resultado encontrado.\n")
        else:
            for i, r in enumerate(results, 1):
                title = r.get('title', 'Sem título')
                url = r.get('url', '')
                snippet = r.get('content', '')
                engines = ', '.join(r.get('engines', []))
                published = r.get('publishedDate', '')

                lines.append(f"### {i}. [{title}]({url})\n")
                if snippet:
                    lines.append(f"{snippet}\n")
                meta = []
                if engines:
                    meta.append(f"Fontes: {engines}")
                if published:
                    meta.append(f"Data: {published}")
                if meta:
                    lines.append(f"*{' | '.join(meta)}*\n")

        # Sugestões
        if suggestions:
            lines.append(f"\n### Sugestões relacionadas\n")
            for s in suggestions:
                lines.append(f"- {s}")

        return {
            "content": [
                {
                    "type": "text",
                    "text": '\n'.join(lines)
                }
            ],
            "isError": False
        }

    def _format_image_results(self, data: dict, max_results: int, query: str) -> dict:
        results = data.get('results', [])[:max_results]

        lines = [f"## Resultados de imagens: \"{query}\"\n"]

        if not results:
            lines.append("Nenhuma imagem encontrada.\n")
        else:
            for i, r in enumerate(results, 1):
                title = r.get('title', 'Sem título')
                img_url = r.get('img_src', r.get('url', ''))
                thumb = r.get('thumbnail_src', '')
                source = r.get('source', r.get('url', ''))
                engines = ', '.join(r.get('engines', []))

                lines.append(f"### {i}. {title}\n")
                if img_url:
                    lines.append(f"![{title}]({img_url})\n")
                if source:
                    lines.append(f"Fonte: {source}\n")
                if engines:
                    lines.append(f"*Engine: {engines}*\n")

        return {
            "content": [
                {
                    "type": "text",
                    "text": '\n'.join(lines)
                }
            ],
            "isError": False
        }

    def _error_response(self, message: str) -> dict:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Erro: {message}"
                }
            ],
            "isError": True
        }

    # ------------------------------------------------------------------
    # MCP Protocol Handlers
    # ------------------------------------------------------------------
    def handle_mcp_initialize(self, request_id):
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": self.server_info,
                "capabilities": self.capabilities
            }
        }

    def handle_tools_list(self, request_id):
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": TOOLS
            }
        }

    async def handle_tools_call(self, request_id, params):
        name = params.get('name', '')
        arguments = params.get('arguments', {})
        result = await self.execute_tool(name, arguments)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }

    async def handle_jsonrpc(self, body: dict) -> dict:
        method = body.get('method', '')
        request_id = body.get('id', str(uuid.uuid4()))
        params = body.get('params', {})

        if method == 'initialize':
            return self.handle_mcp_initialize(request_id)
        elif method == 'tools/list':
            return self.handle_tools_list(request_id)
        elif method == 'tools/call':
            return await self.handle_tools_call(request_id, params)
        elif method == 'notifications/initialized':
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Método não encontrado: {method}"
                }
            }

    # ------------------------------------------------------------------
    # HTTP Handlers
    # ------------------------------------------------------------------
    async def handle_health(self, request):
        """Health check endpoint."""
        healthy = False
        try:
            async with self.session.get(f"{Config.SEARXNG_URL}/") as resp:
                healthy = resp.status == 200
        except Exception:
            pass

        status_code = 200 if healthy else 503
        return web.json_response({
            "status": "ok" if healthy else "degraded",
            "server": self.server_info,
            "searxng_url": Config.SEARXNG_URL,
            "searxng_reachable": healthy,
            "timestamp": datetime.utcnow().isoformat()
        }, status=status_code)

    async def handle_mcp_post(self, request):
        """JSON-RPC endpoint (direto)."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"}
            }, status=400)

        response = await self.handle_jsonrpc(body)
        return web.json_response(response)

    # ------------------------------------------------------------------
    # SSE Transport (padrão MCP - compatível com n8n)
    #
    # Fluxo:
    #   1. Cliente faz GET /sse → recebe evento "endpoint" com URL do POST
    #   2. Cliente faz POST /messages?sessionId=xxx com JSON-RPC
    #   3. Servidor responde via SSE stream com evento "message"
    # ------------------------------------------------------------------
    async def handle_sse(self, request):
        """GET /sse - Estabelece conexão SSE e envia o endpoint para POST."""
        session_id = str(uuid.uuid4())
        queue: asyncio.Queue = asyncio.Queue()
        self._sse_sessions[session_id] = queue

        logger.info(f"Nova sessão SSE: {session_id}")

        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
            }
        )
        await response.prepare(request)

        # Envia o endpoint para o cliente postar mensagens
        endpoint_url = f"/messages?sessionId={session_id}"
        await response.write(f"event: endpoint\ndata: {endpoint_url}\n\n".encode('utf-8'))

        try:
            while True:
                try:
                    # Espera mensagem na fila (com timeout p/ detectar desconexão)
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    data = json.dumps(message, ensure_ascii=False)
                    await response.write(f"event: message\ndata: {data}\n\n".encode('utf-8'))
                except asyncio.TimeoutError:
                    # Envia keep-alive
                    await response.write(": keep-alive\n\n".encode('utf-8'))
        except (ConnectionResetError, ConnectionAbortedError, asyncio.CancelledError):
            logger.info(f"Sessão SSE encerrada: {session_id}")
        finally:
            self._sse_sessions.pop(session_id, None)

        return response

    async def handle_messages(self, request):
        """POST /messages?sessionId=xxx - Recebe JSON-RPC e responde via SSE."""
        session_id = request.query.get('sessionId', '')
        if not session_id or session_id not in self._sse_sessions:
            return web.json_response(
                {"error": "Sessão SSE não encontrada. Conecte primeiro em GET /sse"},
                status=400
            )

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
                status=400
            )

        # Processa e envia resposta pela fila SSE
        response = await self.handle_jsonrpc(body)
        queue = self._sse_sessions.get(session_id)
        if queue:
            await queue.put(response)

        return web.json_response({"status": "accepted"}, status=202)

    # ------------------------------------------------------------------
    # App Factory
    # ------------------------------------------------------------------
    def create_app(self) -> web.Application:
        app = web.Application()

        # Health
        app.router.add_get('/health', self.handle_health)

        # JSON-RPC direto
        app.router.add_post('/mcp', self.handle_mcp_post)

        # SSE Transport (padrão MCP - para n8n, Claude Desktop, etc)
        app.router.add_get('/sse', self.handle_sse)
        app.router.add_post('/messages', self.handle_messages)

        # CORS
        cors = aiohttp_cors.setup(app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods=["GET", "POST", "OPTIONS"]
            )
        })
        for route in list(app.router.routes()):
            cors.add(route)

        app.on_startup.append(lambda _: self.start_session())
        app.on_cleanup.append(lambda _: self.close_session())

        return app


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='MCP SearXNG Server')
    parser.add_argument('--host', default=Config.HOST, help='Host to bind')
    parser.add_argument('--port', type=int, default=Config.PORT, help='Port to bind')
    args = parser.parse_args()

    server = MCPSearXNGServer()
    app = server.create_app()

    logger.info(f"Iniciando MCP SearXNG Server em {args.host}:{args.port}")
    logger.info(f"SearXNG URL: {Config.SEARXNG_URL}")
    logger.info(f"Endpoints: /health, /mcp, /sse, /messages")
    logger.info(f"Tools: {', '.join(t['name'] for t in TOOLS)}")

    web.run_app(app, host=args.host, port=args.port)


if __name__ == '__main__':
    main()
