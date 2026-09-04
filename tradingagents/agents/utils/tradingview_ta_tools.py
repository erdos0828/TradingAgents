"""TradingView technical analysis tool for TradingAgents.

Wraps the third-party `tradingview-ta` package to expose an aggregated
oscillator / moving-average consensus that the Market Analyst can call like
any other data tool.  Results are cached in the shared SQLite cache keyed by
(symbol, date) so repeated analyses for the same day do not hit the network.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

import yfinance as yf
from langchain_core.tools import tool
from tradingview_ta import Interval, TA_Handler

from tradingagents.dataflows.symbol_utils import normalize_symbol
from tradingagents.dataflows.tradingview_ta_cache import load_ta, store_ta

logger = logging.getLogger(__name__)

# Yahoo Finance -> TradingView exchange names for US equities.
_US_EXCHANGE_MAP = {
    "NMS": "NASDAQ",  # Nasdaq Global Select
    "NGM": "NASDAQ",  # Nasdaq Global Market
    "NAS": "NASDAQ",
    "NYQ": "NYSE",
    "ASE": "AMEX",
    "PCX": "NYSE",    # NYSE Arca/ Pacific
    "BATS": "BATS",
}


def _resolve_tradingview_params(symbol: str) -> dict[str, str]:
    """Map a ticker to TradingView screener/exchange parameters.

    A-shares are routed to ``china`` with the exchange suffix stripped.
    US equities fall back to yfinance ``info`` for the exchange.  Any
    resolution failure is logged and falls back to ``america/NASDAQ`` so
    the tool can still attempt a request.
    """
    norm = normalize_symbol(symbol)

    if norm.endswith(".SS"):
        return {"screener": "china", "exchange": "SSE", "symbol": norm[:-3]}
    if norm.endswith(".SZ"):
        return {"screener": "china", "exchange": "SZSE", "symbol": norm[:-3]}

    try:
        info = yf.Ticker(norm).info or {}
        exchange = info.get("exchange", "")
        tv_exchange = _US_EXCHANGE_MAP.get(exchange, exchange) or "NASDAQ"
    except Exception as exc:  # noqa: BLE001 — fail open with a sensible fallback
        logger.warning("Could not resolve exchange for %s (%s): %s", symbol, norm, exc)
        tv_exchange = "NASDAQ"

    return {"screener": "america", "exchange": tv_exchange, "symbol": norm}


def _fetch_analysis(symbol: str, curr_date: str) -> dict[str, Any]:
    """Fetch fresh TradingView TA data from the network and cache it."""
    params = _resolve_tradingview_params(symbol)
    logger.info(
        "Fetching TradingView TA for %s on %s (screener=%s, exchange=%s)",
        symbol,
        curr_date,
        params["screener"],
        params["exchange"],
    )

    handler = TA_Handler(
        symbol=params["symbol"],
        screener=params["screener"],
        exchange=params["exchange"],
        interval=Interval.INTERVAL_1_DAY,
    )
    analysis = handler.get_analysis()
    summary = analysis.summary

    data = {
        "recommendation": summary["RECOMMENDATION"],
        "buy_votes": summary["BUY"],
        "sell_votes": summary["SELL"],
        "neutral_votes": summary["NEUTRAL"],
        "oscillators": dict(analysis.oscillators["COMPUTE"]),
        "moving_averages": dict(analysis.moving_averages["COMPUTE"]),
    }
    store_ta(symbol, curr_date, data)
    return data


def _format_analysis(data: dict[str, Any], curr_date: str) -> str:
    """Render cached/fresh TA data into the tool's text output."""
    lines = [
        f"TradingView Technical Analysis ({curr_date}, daily):",
        f"Overall recommendation: {data['recommendation']}",
        "Votes - BUY: {}, SELL: {}, NEUTRAL: {}".format(
            data["buy_votes"], data["sell_votes"], data["neutral_votes"]
        ),
        "",
        "Oscillator votes:",
    ]
    for name, vote in data["oscillators"].items():
        lines.append(f"  {name}: {vote}")
    lines.extend(["", "Moving average votes:"])
    for name, vote in data["moving_averages"].items():
        lines.append(f"  {name}: {vote}")
    return "\n".join(lines)


@tool
def get_tradingview_ta(
    symbol: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
) -> str:
    """Retrieve TradingView's aggregated technical analysis for a ticker.

    Uses the daily interval and returns the overall recommendation plus the
    oscillator and moving-average vote breakdown.  Results are cached in
    SQLite by (symbol, date); a cache hit avoids a network request.  Network
    or mapping failures are raised (not swallowed) so the pipeline fails fast
    and the error is logged by the caller.
    """
    cached = load_ta(symbol, curr_date)
    if cached is not None:
        logger.info("Using cached TradingView TA for %s on %s", symbol, curr_date)
        return _format_analysis(cached, curr_date)

    data = _fetch_analysis(symbol, curr_date)
    return _format_analysis(data, curr_date)
