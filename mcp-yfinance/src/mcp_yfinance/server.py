"""MCP server entry point exposing yfinance tools over HTTP/SSE."""

from __future__ import annotations

import argparse
import logging

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
import uvicorn

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

mcp = FastMCP("yfinance")

mcp.add_tool(get_stock_price)
mcp.add_tool(get_stock_history)
mcp.add_tool(get_stock_info)
mcp.add_tool(get_financials)
mcp.add_tool(get_recommendations)
mcp.add_tool(search_tickers)


def create_starlette_app() -> Starlette:
    """Build a Starlette app that serves the MCP server over SSE."""
    # FastMCP.sse() exposes the standard MCP HTTP/SSE endpoints.
    # GET /sse   - establish the Server-Sent Events stream
    # POST /messages/ - JSON-RPC messages over the active SSE session
    sse = mcp.sse()

    async def homepage(_request: Request) -> PlainTextResponse:
        return PlainTextResponse(
            f"mcp-yfinance v{__version__}\n"
            "SSE endpoint: GET /sse\n"
            "POST messages: /messages/\n"
        )

    routes = [
        Route("/", homepage),
        Route("/sse", endpoint=sse.handle_get),
        Route("/messages/", endpoint=sse.handle_post),
    ]
    return Starlette(routes=routes)


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
