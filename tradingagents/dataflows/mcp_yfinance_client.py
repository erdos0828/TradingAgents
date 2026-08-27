"""Synchronous MCP client for the remote yfinance MCP server.

Environment variables:
    MCP_YFINANCE_URL: SSE endpoint of the yfinance MCP server
                      (default: http://localhost:8080/sse).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from collections.abc import Coroutine
from typing import Any

import httpx
import pandas as pd
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)

DEFAULT_MCP_YFINANCE_URL = "http://localhost:8080/sse"
_MCP_YFINANCE_URL = os.getenv("MCP_YFINANCE_URL", DEFAULT_MCP_YFINANCE_URL)


def _run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async coroutine from synchronous code.

    ``asyncio.run`` is used when no event loop is running. If the caller is
    already inside a running loop (e.g. an async LangGraph node), the coroutine
    is executed in a dedicated background thread with its own loop.
    """
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # Already inside an event loop; spin up a separate thread/loop.
        result: list[Any] = []
        exception: list[BaseException] = []

        def _runner() -> None:
            loop = asyncio.new_event_loop()
            try:
                result.append(loop.run_until_complete(coro))
            except BaseException as exc:  # noqa: BLE001
                exception.append(exc)
            finally:
                loop.close()

        thread = threading.Thread(target=_runner)
        thread.start()
        thread.join()
        if exception:
            raise exception[0] from None
        return result[0]


def _httpx_client_factory(**kwargs: Any) -> httpx.AsyncClient:
    """Create an httpx client that ignores environment proxy variables.

    This prevents stale ``HTTP_PROXY``/``ALL_PROXY`` values from routing MCP
    requests through a local proxy that cannot reach the remote SSE endpoint.
    """
    kwargs.setdefault("trust_env", False)
    kwargs.setdefault("timeout", 60.0)
    return httpx.AsyncClient(**kwargs)


def _is_retriable_error(exc: BaseException) -> bool:
    """Return True if *exc* (or an ExceptionGroup wrapping it) is transient."""
    if hasattr(exc, "exceptions"):
        return any(_is_retriable_error(e) for e in exc.exceptions)  # type: ignore[attr-defined]
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException, OSError))


async def _call_tool_async(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Make a single tool call through the MCP SSE transport."""
    url = _MCP_YFINANCE_URL
    logger.debug("MCP call %s to %s with args %s", tool_name, url, arguments)
    async with (
        sse_client(url, httpx_client_factory=_httpx_client_factory) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        response = await session.call_tool(tool_name, arguments=arguments)
        if not response.content:
            raise ValueError(f"MCP tool {tool_name!r} returned empty content")
        text = response.content[0].text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"_raw": text}


def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Call a remote yfinance MCP tool and return the parsed JSON payload.

    Retries transient network errors with exponential backoff to survive
    intermittent connectivity to the remote MCP server during batch runs.
    """
    max_retries = 3
    last_exc: BaseException | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return _run_async(_call_tool_async(tool_name, arguments))
        except BaseException as exc:
            last_exc = exc
            if attempt == max_retries or not _is_retriable_error(exc):
                raise
            delay = 2 ** (attempt - 1)
            logger.warning(
                "MCP call %s failed on attempt %d/%d: %s; retrying in %ds",
                tool_name,
                attempt,
                max_retries,
                exc,
                delay,
            )
            time.sleep(delay)
    # Unreachable in practice, but keeps mypy happy.
    raise last_exc  # pragma: no cover


def _records_to_dataframe(records: list[dict[str, Any]], date_col: str = "date") -> pd.DataFrame:
    """Convert a list of record dicts into a DataFrame with a DatetimeIndex."""
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col]).set_index(date_col)
        df.index.name = None
    return df


def mcp_get_stock_info(ticker: str) -> dict[str, Any]:
    """Fetch company/quote metadata via the MCP ``get_stock_info`` tool."""
    return call_mcp_tool("get_stock_info", {"ticker": ticker}) or {}


def mcp_get_stock_history(
    ticker: str,
    *,
    period: str | None = None,
    interval: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Fetch historical OHLCV via the MCP ``get_stock_history`` tool."""
    args: dict[str, Any] = {"ticker": ticker}
    if period is not None:
        args["period"] = period
    if interval is not None:
        args["interval"] = interval
    if start is not None:
        args["start"] = start
    if end is not None:
        args["end"] = end

    payload = call_mcp_tool("get_stock_history", args)
    records = payload.get("data", []) if isinstance(payload, dict) else []
    return _records_to_dataframe(records)


def mcp_download_stock_data(
    tickers: str,
    *,
    start: str | None = None,
    end: str | None = None,
    period: str | None = None,
    interval: str | None = None,
    auto_adjust: bool = True,
    multi_level_index: bool = False,
) -> pd.DataFrame:
    """Batch-download OHLCV via the MCP ``download_stock_data`` tool."""
    args: dict[str, Any] = {
        "tickers": tickers,
        "auto_adjust": auto_adjust,
        "multi_level_index": multi_level_index,
    }
    if start is not None:
        args["start"] = start
    if end is not None:
        args["end"] = end
    if period is not None:
        args["period"] = period
    if interval is not None:
        args["interval"] = interval

    payload = call_mcp_tool("download_stock_data", args)
    records = payload.get("data", []) if isinstance(payload, dict) else []
    return _records_to_dataframe(records)


def mcp_get_financials(
    ticker: str, statement: str = "income", freq: str = "annual"
) -> pd.DataFrame:
    """Fetch a financial statement via the MCP ``get_financials`` tool."""
    payload = call_mcp_tool(
        "get_financials", {"ticker": ticker, "statement": statement, "freq": freq}
    )
    records = payload.get("data", []) if isinstance(payload, dict) else []
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records).set_index("date").T
    df.columns = pd.to_datetime(df.columns, errors="coerce")
    return df


def mcp_get_recommendations(ticker: str) -> pd.DataFrame:
    """Fetch analyst recommendations via the MCP ``get_recommendations`` tool."""
    payload = call_mcp_tool("get_recommendations", {"ticker": ticker})
    records = payload.get("recommendations", []) if isinstance(payload, dict) else []
    return _records_to_dataframe(records)


def mcp_get_news(ticker: str, count: int = 20) -> list[dict[str, Any]]:
    """Fetch ticker news via the MCP ``get_news`` tool."""
    payload = call_mcp_tool("get_news", {"ticker": ticker, "count": count})
    return payload.get("news", []) if isinstance(payload, dict) else []


def mcp_search_news(query: str, count: int = 10) -> list[dict[str, Any]]:
    """Fetch global/macro news via the MCP ``search_news`` tool."""
    payload = call_mcp_tool("search_news", {"query": query, "count": count})
    return payload.get("news", []) if isinstance(payload, dict) else []


def mcp_get_insider_transactions(ticker: str) -> pd.DataFrame:
    """Fetch insider transactions via the MCP ``get_insider_transactions`` tool."""
    payload = call_mcp_tool("get_insider_transactions", {"ticker": ticker})
    records = payload.get("data", []) if isinstance(payload, dict) else []
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)
