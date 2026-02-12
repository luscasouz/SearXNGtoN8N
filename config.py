import os


class Config:
    SEARXNG_URL = os.getenv('SEARXNG_URL', 'http://searxng:8080')
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', '8091'))
    MCP_SERVER_NAME = os.getenv('MCP_SERVER_NAME', 'searxng-mcp-server')
    MCP_SERVER_VERSION = os.getenv('MCP_SERVER_VERSION', '1.0.0')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    DEFAULT_MAX_RESULTS = int(os.getenv('DEFAULT_MAX_RESULTS', '10'))
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
