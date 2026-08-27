"""MCP server entry point exposing yfinance tools over HTTP/SSE."""

from __future__ import annotations

import argparse
import logging
from typing import Any

import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Mount

from mcp_yfinance import __version__
from mcp_yfinance.tools import (
    get_financials,
    get_recommendations,
    get_stock_history,
    get_stock_info,
    get_stock_price,
    search_tickers,
)

logger = logging.getLogger("mcp-yfinance")

server = Server("yfinance")
sse = SseServerTransport("/messages/")

TOOLS = [
    Tool(
        name="get_stock_price",
        description="Return the latest OHLCV price and change for a ticker.",
        inputSchema={
            "type": "object",
            "properties": {"ticker": {"type": "string", "description": "Stock symbol, e.g. AAPL or 600519.SS"}},
            "required": ["ticker"],
        },
    ),
    Tool(
        name="get_stock_history",
        description="Return historical OHLCV data for a ticker.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "period": {
                    "type": "string",
                    "description": "yfinance period such as 1d, 5d, 1mo, 3mo, 6mo, 1y, ytd, max",
                    "default": "1mo",
                },
                "interval": {
                    "type": "string",
                    "description": "yfinance interval such as 1m, 15m, 1h, 1d, 1wk",
                    "default": "1d",
                },
                "start": {"type": "string", "description": "Start date YYYY-MM-DD", "default": None},
                "end": {"type": "string", "description": "End date YYYY-MM-DD", "default": None},
            },
            "required": ["ticker"],
        },
    ),
    Tool(
        name="get_stock_info",
        description="Return company/quote metadata for a ticker.",
        inputSchema={
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    ),
    Tool(
        name="get_financials",
        description="Return annual financial statements for a ticker.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "statement": {
                    "type": "string",
                    "enum": ["income", "balance", "cash"],
                    "default": "income",
                },
            },
            "required": ["ticker"],
        },
    ),
    Tool(
        name="get_recommendations",
        description="Return recent analyst recommendations for a ticker.",
        inputSchema={
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    ),
    Tool(
        name="search_tickers",
        description="Search for tickers by company name or symbol.",
        inputSchema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    ),
]

TOOL_MAP = {
    "get_stock_price": get_stock_price,
    "get_stock_history": get_stock_history,
    "get_stock_info": get_stock_info,
    "get_financials": get_financials,
    "get_recommendations": get_recommendations,
    "search_tickers": search_tickers,
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name not in TOOL_MAP:
        raise ValueError(f"Unknown tool: {name}")
    try:
        result = TOOL_MAP[name](**arguments)
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        result = f"Error running {name}: {exc}"
    return [TextContent(type="text", text=result)]


async def mcp_asgi_app(scope: dict, receive: Any, send: Any) -> None:
    """Pure ASGI app handling MCP SSE and message endpoints.

    Using a single mounted ASGI app avoids Starlette's Request wrapping,
    which in some versions only passes ``request`` regardless of signature.
    """
    if scope.get("type") != "http":
        return

    path = scope.get("path", "")
    method = scope.get("method", "")

    if path == "/" and method == "GET":
        response = PlainTextResponse(
            f"mcp-yfinance v{__version__}\n"
            "SSE endpoint: GET /sse\n"
            "POST messages: /messages/\n"
        )
        await response(scope, receive, send)
    elif path == "/sse" and method == "GET":
        async with sse.connect_sse(scope, receive, send) as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )
    elif path == "/messages/" and method == "POST":
        await sse.handle_post_message(scope, receive, send)
    else:
        response = PlainTextResponse("Not found", status_code=404)
        await response(scope, receive, send)


def create_starlette_app() -> Starlette:
    return Starlette(routes=[Mount("/", app=mcp_asgi_app)])


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP server for yfinance market data")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8080, help="Bind port")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    app = create_starlette_app()
    logger.info("Starting mcp-yfinance %s on %s:%s", __version__, args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level.lower())


if __name__ == "__main__":
    main()
