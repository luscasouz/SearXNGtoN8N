# MCP SearXNG Server

[English](#english) | [Portugues](#portugues)

---

<a name="english"></a>

## English

A **Model Context Protocol (MCP)** server that exposes [SearXNG](https://github.com/searxng/searxng) as AI-ready tools. Search the web, news, and images through a privacy-focused metasearch engine — accessible from **n8n**, **Claude Desktop**, and any MCP-compatible client.

```
┌──────────────────────────────────┐
│  Claude Desktop / n8n / Client   │
└──────────────┬───────────────────┘
               │  MCP (JSON-RPC 2.0)
       ┌───────┴────────┐
       │  mcp-searxng    │  :8091
       └───────┬────────┘
               │
       ┌───────┴────────┐
       │    SearXNG      │  :8080
       └────────────────┘
        Google, Bing, DuckDuckGo,
        Brave, Wikipedia...
```

### Features

- **4 MCP Tools** — `web_search`, `news_search`, `images_search`, `fetch_page_content`
- **Dual Transport** — HTTP/SSE (for n8n and web clients) + Stdio (for Claude Desktop)
- **Privacy First** — Uses SearXNG, no tracking, no API keys required from search engines
- **n8n Ready** — Works out of the box with n8n's MCP Client node via SSE transport
- **Multi-Engine** — Aggregates results from Google, Bing, DuckDuckGo, Brave, Wikipedia, and more
- **Page Fetcher** — Fetch any URL and get clean Markdown content (scripts, nav, ads removed)
- **100% Async** — Built on `aiohttp` for high concurrency
- **Docker Ready** — Single `docker compose up` to run everything
- **Health Checks** — Built-in `/health` endpoint with SearXNG connectivity verification

### Tools

| Tool | Description |
|------|-------------|
| `web_search` | General web search with category, engine, language, time range, and safe search filters |
| `news_search` | Search recent news articles with time range filtering |
| `images_search` | Search images across multiple engines |
| `fetch_page_content` | Fetch a URL and convert its content to clean Markdown |

### Quick Start

#### Docker Compose (Recommended)

```bash
git clone https://github.com/luscasouz/SearXNGtoN8N.git
cd SearXNGtoN8N

# IMPORTANT: Change the secret key before running
# Edit searxng/settings.yml and replace "change-me-to-a-random-string"
# with a random string (e.g.: openssl rand -hex 32)

docker compose up -d
```

The server will be available at `http://localhost:8091`.

#### Verify it's running

```bash
curl http://localhost:8091/health
```

Expected response:
```json
{
  "status": "ok",
  "server": {"name": "searxng-mcp-server", "version": "1.0.0"},
  "searxng_reachable": true
}
```

### Integration with n8n

This server is **fully compatible with n8n's MCP Client node** using SSE transport.

#### Setup in n8n

1. Add an **MCP Client** node to your workflow
2. Set the **SSE URL** to:
   ```
   http://mcp-searxng:8091/sse
   ```
   > If n8n runs on the same Docker network, use the container name. Otherwise, use your server IP/hostname.
3. The tools (`web_search`, `news_search`, `images_search`, `fetch_page_content`) will be automatically discovered
4. Connect the MCP Client node to an **AI Agent** node to let the AI use web search

#### Example n8n Architecture

```
[Chat Trigger] → [AI Agent] → [MCP Client (mcp-searxng)]
                      ↓
               [LLM (OpenAI/Ollama/etc)]
```

> **Tip:** If your n8n instance runs in Docker, make sure both containers share the same Docker network. You can add `mcp-net` as an external network in your n8n docker-compose.

### Integration with Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "searxng": {
      "command": "python3",
      "args": ["path/to/mcp_stdio_server.py"],
      "env": {
        "SEARXNG_URL": "http://localhost:8890"
      }
    }
  }
}
```

> Make sure SearXNG is accessible at the URL specified. If using Docker, the SearXNG instance is exposed on port `8890`.

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with SearXNG connectivity status |
| `/mcp` | POST | Direct JSON-RPC 2.0 endpoint |
| `/sse` | GET | SSE stream for MCP transport (n8n, web clients) |
| `/messages` | POST | SSE message endpoint (requires `sessionId` query param) |

### Configuration

All settings can be configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARXNG_URL` | `http://searxng:8080` | SearXNG instance URL |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8091` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `DEFAULT_MAX_RESULTS` | `10` | Default number of results per search |
| `REQUEST_TIMEOUT` | `30` | HTTP request timeout in seconds |

### Running Without Docker

```bash
# Install dependencies
pip install -r requirements_api.txt

# Make sure you have a SearXNG instance running
export SEARXNG_URL=http://localhost:8890

# Run the HTTP/SSE server
python3 mcp_http_sse_server.py --port 8091

# Or run the Stdio server (for Claude Desktop)
python3 mcp_stdio_server.py
```

### Project Structure

```
.
├── mcp_http_sse_server.py   # Main server (HTTP/SSE transport)
├── mcp_stdio_server.py      # Stdio transport (Claude Desktop)
├── config.py                # Configuration via environment variables
├── requirements_api.txt     # Python dependencies
├── Dockerfile               # Container image
├── docker-compose.yml       # Full stack (MCP server + SearXNG)
└── searxng/
    └── settings.yml         # SearXNG configuration
```

### Example Usage

#### Direct JSON-RPC call

```bash
curl -X POST http://localhost:8091/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "web_search",
      "arguments": {
        "query": "Model Context Protocol",
        "max_results": 5
      }
    }
  }'
```

#### List available tools

```bash
curl -X POST http://localhost:8091/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

#### Fetch page content

```bash
curl -X POST http://localhost:8091/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "fetch_page_content",
      "arguments": {
        "url": "https://docs.searxng.org",
        "max_length": 5000
      }
    }
  }'
```

### SearXNG Search Engines

The default configuration enables:

| Engine | Category |
|--------|----------|
| Google | General |
| Bing | General |
| DuckDuckGo | General |
| Brave | General |
| Wikipedia | General |
| Google News | News |

You can customize engines by editing `searxng/settings.yml`.

### Security Notes

- **Change the secret key** in `searxng/settings.yml` before deploying
- The server has **no built-in authentication** — deploy behind a reverse proxy (nginx, Traefik) for production use
- CORS is configured to allow all origins by default — restrict it if exposing publicly

---

<a name="portugues"></a>

## Portugues

Um servidor **Model Context Protocol (MCP)** que expoe o [SearXNG](https://github.com/searxng/searxng) como ferramentas prontas para IA. Busque na web, noticias e imagens atraves de um metabuscador focado em privacidade — acessivel pelo **n8n**, **Claude Desktop** e qualquer cliente compativel com MCP.

```
┌──────────────────────────────────┐
│  Claude Desktop / n8n / Client   │
└──────────────┬───────────────────┘
               │  MCP (JSON-RPC 2.0)
       ┌───────┴────────┐
       │  mcp-searxng    │  :8091
       └───────┬────────┘
               │
       ┌───────┴────────┐
       │    SearXNG      │  :8080
       └────────────────┘
        Google, Bing, DuckDuckGo,
        Brave, Wikipedia...
```

### Funcionalidades

- **4 Ferramentas MCP** — `web_search`, `news_search`, `images_search`, `fetch_page_content`
- **Transporte Duplo** — HTTP/SSE (para n8n e clientes web) + Stdio (para Claude Desktop)
- **Privacidade** — Usa SearXNG, sem rastreamento, sem necessidade de API keys dos buscadores
- **Pronto para n8n** — Funciona direto com o node MCP Client do n8n via transporte SSE
- **Multi-Engine** — Agrega resultados do Google, Bing, DuckDuckGo, Brave, Wikipedia e mais
- **Leitor de Paginas** — Busca qualquer URL e retorna conteudo limpo em Markdown (sem scripts, nav, ads)
- **100% Async** — Construido com `aiohttp` para alta concorrencia
- **Docker Ready** — Um unico `docker compose up` para rodar tudo
- **Health Checks** — Endpoint `/health` integrado com verificacao de conectividade do SearXNG

### Ferramentas

| Ferramenta | Descricao |
|------------|-----------|
| `web_search` | Busca geral na web com filtros de categoria, engine, idioma, periodo e safe search |
| `news_search` | Busca noticias recentes com filtro temporal |
| `images_search` | Busca imagens em multiplas engines |
| `fetch_page_content` | Busca uma URL e converte o conteudo para Markdown limpo |

### Inicio Rapido

#### Docker Compose (Recomendado)

```bash
git clone https://github.com/luscasouz/SearXNGtoN8N.git
cd SearXNGtoN8N

# IMPORTANTE: Altere a secret key antes de rodar
# Edite searxng/settings.yml e substitua "change-me-to-a-random-string"
# por uma string aleatoria (ex: openssl rand -hex 32)

docker compose up -d
```

O servidor estara disponivel em `http://localhost:8091`.

#### Verificar se esta rodando

```bash
curl http://localhost:8091/health
```

Resposta esperada:
```json
{
  "status": "ok",
  "server": {"name": "searxng-mcp-server", "version": "1.0.0"},
  "searxng_reachable": true
}
```

### Integracao com n8n

Este servidor e **totalmente compativel com o node MCP Client do n8n** usando transporte SSE.

#### Configuracao no n8n

1. Adicione um node **MCP Client** no seu workflow
2. Configure a **SSE URL** para:
   ```
   http://mcp-searxng:8091/sse
   ```
   > Se o n8n roda na mesma rede Docker, use o nome do container. Caso contrario, use o IP/hostname do servidor.
3. As ferramentas (`web_search`, `news_search`, `images_search`, `fetch_page_content`) serao descobertas automaticamente
4. Conecte o node MCP Client a um node **AI Agent** para que a IA use a busca web

#### Exemplo de Arquitetura n8n

```
[Chat Trigger] → [AI Agent] → [MCP Client (mcp-searxng)]
                      ↓
               [LLM (OpenAI/Ollama/etc)]
```

> **Dica:** Se sua instancia n8n roda em Docker, certifique-se de que ambos os containers compartilham a mesma rede Docker. Voce pode adicionar `mcp-net` como rede externa no docker-compose do seu n8n.

### Integracao com Claude Desktop

Adicione na configuracao do Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "searxng": {
      "command": "python3",
      "args": ["caminho/para/mcp_stdio_server.py"],
      "env": {
        "SEARXNG_URL": "http://localhost:8890"
      }
    }
  }
}
```

> Certifique-se de que o SearXNG esta acessivel na URL especificada. Se estiver usando Docker, a instancia do SearXNG esta exposta na porta `8890`.

### Endpoints da API

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `/health` | GET | Health check com status de conectividade do SearXNG |
| `/mcp` | POST | Endpoint JSON-RPC 2.0 direto |
| `/sse` | GET | Stream SSE para transporte MCP (n8n, clientes web) |
| `/messages` | POST | Endpoint de mensagens SSE (requer parametro `sessionId`) |

### Configuracao

Todas as configuracoes podem ser feitas via variaveis de ambiente:

| Variavel | Padrao | Descricao |
|----------|--------|-----------|
| `SEARXNG_URL` | `http://searxng:8080` | URL da instancia SearXNG |
| `HOST` | `0.0.0.0` | Endereco de bind do servidor |
| `PORT` | `8091` | Porta do servidor |
| `LOG_LEVEL` | `INFO` | Nivel de log (DEBUG, INFO, WARNING, ERROR) |
| `DEFAULT_MAX_RESULTS` | `10` | Numero padrao de resultados por busca |
| `REQUEST_TIMEOUT` | `30` | Timeout de requisicao HTTP em segundos |

### Rodando Sem Docker

```bash
# Instalar dependencias
pip install -r requirements_api.txt

# Certifique-se de ter uma instancia SearXNG rodando
export SEARXNG_URL=http://localhost:8890

# Rodar o servidor HTTP/SSE
python3 mcp_http_sse_server.py --port 8091

# Ou rodar o servidor Stdio (para Claude Desktop)
python3 mcp_stdio_server.py
```

### Estrutura do Projeto

```
.
├── mcp_http_sse_server.py   # Servidor principal (transporte HTTP/SSE)
├── mcp_stdio_server.py      # Transporte Stdio (Claude Desktop)
├── config.py                # Configuracao via variaveis de ambiente
├── requirements_api.txt     # Dependencias Python
├── Dockerfile               # Imagem do container
├── docker-compose.yml       # Stack completa (servidor MCP + SearXNG)
└── searxng/
    └── settings.yml         # Configuracao do SearXNG
```

### Exemplos de Uso

#### Chamada JSON-RPC direta

```bash
curl -X POST http://localhost:8091/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "web_search",
      "arguments": {
        "query": "Model Context Protocol",
        "max_results": 5
      }
    }
  }'
```

#### Listar ferramentas disponiveis

```bash
curl -X POST http://localhost:8091/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

#### Buscar conteudo de pagina

```bash
curl -X POST http://localhost:8091/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "fetch_page_content",
      "arguments": {
        "url": "https://docs.searxng.org",
        "max_length": 5000
      }
    }
  }'
```

### Engines de Busca do SearXNG

A configuracao padrao habilita:

| Engine | Categoria |
|--------|-----------|
| Google | Geral |
| Bing | Geral |
| DuckDuckGo | Geral |
| Brave | Geral |
| Wikipedia | Geral |
| Google News | Noticias |

Voce pode personalizar as engines editando `searxng/settings.yml`.

### Notas de Seguranca

- **Altere a secret key** em `searxng/settings.yml` antes de fazer deploy
- O servidor **nao possui autenticacao integrada** — use um reverse proxy (nginx, Traefik) para producao
- CORS esta configurado para aceitar todas as origens por padrao — restrinja se for expor publicamente

---

## License / Licenca

This project is licensed under the Apache License 2.0 — see the [LICENSE](LICENSE) file for details.

Este projeto esta licenciado sob a Apache License 2.0 — veja o arquivo [LICENSE](LICENSE) para detalhes.
