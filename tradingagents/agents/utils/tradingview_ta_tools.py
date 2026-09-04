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

# Curated list of raw indicator values exposed to the LLM.  These are the
# most commonly referenced figures when turning a vote-based consensus into
# a nuanced technical view.
_KEY_INDICATORS = [
    # Price / volume
    "close",
    "open",
    "high",
    "low",
    "volume",
    "change",
    # Oscillators
    "RSI",
    "Stoch.K",
    "Stoch.D",
    "CCI20",
    "ADX",
    "AO",
    "Mom",
    "MACD.macd",
    "MACD.signal",
    "Stoch.RSI.K",
    "W.R",
    "BBPower",
    "UO",
    # Moving averages
    "EMA5",
    "SMA5",
    "EMA10",
    "SMA10",
    "EMA20",
    "SMA20",
    "EMA30",
    "SMA30",
    "EMA50",
    "SMA50",
    "EMA100",
    "SMA100",
    "EMA200",
    "SMA200",
    "VWMA",
    "HullMA9",
    # Bands
    "BB.lower",
    "BB.upper",
    "P.SAR",
    # Pivot points (Classic / Fibonacci / Camarilla / Woodie / Demark)
    "Pivot.M.Classic.S3",
    "Pivot.M.Classic.S2",
    "Pivot.M.Classic.S1",
    "Pivot.M.Classic.Middle",
    "Pivot.M.Classic.R1",
    "Pivot.M.Classic.R2",
    "Pivot.M.Classic.R3",
    "Pivot.M.Fibonacci.S3",
    "Pivot.M.Fibonacci.S2",
    "Pivot.M.Fibonacci.S1",
    "Pivot.M.Fibonacci.Middle",
    "Pivot.M.Fibonacci.R1",
    "Pivot.M.Fibonacci.R2",
    "Pivot.M.Fibonacci.R3",
    "Pivot.M.Camarilla.S3",
    "Pivot.M.Camarilla.S2",
    "Pivot.M.Camarilla.S1",
    "Pivot.M.Camarilla.Middle",
    "Pivot.M.Camarilla.R1",
    "Pivot.M.Camarilla.R2",
    "Pivot.M.Camarilla.R3",
    "Pivot.M.Woodie.S3",
    "Pivot.M.Woodie.S2",
    "Pivot.M.Woodie.S1",
    "Pivot.M.Woodie.Middle",
    "Pivot.M.Woodie.R1",
    "Pivot.M.Woodie.R2",
    "Pivot.M.Woodie.R3",
    "Pivot.M.Demark.S1",
    "Pivot.M.Demark.Middle",
    "Pivot.M.Demark.R1",
]


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


def _extract_key_indicators(indicators: dict[str, Any]) -> dict[str, Any]:
    """Return a subset of raw indicator values useful for the report."""
    extracted: dict[str, Any] = {}
    for key in _KEY_INDICATORS:
        value = indicators.get(key)
        if value is not None:
            extracted[key] = value
    return extracted


def _format_value(value: Any) -> str:
    """Format a single indicator value for readability."""
    if isinstance(value, (int, float)):
        # Large numbers (volume) get commas; prices/small numbers stay compact.
        if abs(value) >= 1_000_000:
            return f"{value:,.0f}"
        if isinstance(value, int):
            return str(value)
        return f"{value:.4f}" if abs(value) < 0.1 else f"{value:.2f}"
    return str(value)


def _format_pivot_table(indicators: dict[str, Any]) -> list[str]:
    """Format pivot point levels (Classic/Fibonacci/Camarilla/Woodie/DM) into a table."""
    methods = {
        "Classic": "Pivot.M.Classic.",
        "Fibonacci": "Pivot.M.Fibonacci.",
        "Camarilla": "Pivot.M.Camarilla.",
        "Woodie": "Pivot.M.Woodie.",
        "DM": "Pivot.M.Demark.",
    }
    # TradingView names the pivot point "Middle" rather than "P".
    level_display = ["S3", "S2", "S1", "P", "R1", "R2", "R3"]
    level_keys = ["S3", "S2", "S1", "Middle", "R1", "R2", "R3"]

    has_pivots = any(
        indicators.get(prefix + key) is not None
        for prefix in methods.values()
        for key in level_keys
        if key != "Middle" or "Demark" not in prefix
    )
    if not has_pivots:
        return []

    lines = ["", "Pivot points:"]
    header = f"{'':<10}" + "".join(f"{lvl:>10}" for lvl in level_display)
    lines.append(header)
    for name, prefix in methods.items():
        row: list[str] = []
        for key in level_keys:
            if name == "DM" and key in ("S3", "S2", "R2", "R3"):
                row.append("—")
                continue
            full_key = prefix + key
            value = indicators.get(full_key)
            row.append(_format_value(value) if value is not None else "—")
        lines.append(f"{name:<10}" + "".join(f"{v:>10}" for v in row))
    return lines


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
        "indicators": _extract_key_indicators(analysis.indicators),
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

    indicators = data.get("indicators") or {}
    if indicators:
        lines.extend(["", "Key indicator values:"])

        price_vol = {
            k: indicators.get(k)
            for k in ("open", "high", "low", "close", "volume", "change")
            if indicators.get(k) is not None
        }
        if price_vol:
            parts = [f"{k}={_format_value(v)}" for k, v in price_vol.items()]
            lines.append(f"  Price/Volume: {'  '.join(parts)}")

        oscillator_keys = [
            "RSI", "Stoch.K", "Stoch.D", "CCI20", "ADX", "AO", "Mom",
            "MACD.macd", "MACD.signal", "Stoch.RSI.K", "W.R", "BBPower", "UO",
        ]
        osc_parts = [
            f"{k}={_format_value(indicators[k])}"
            for k in oscillator_keys
            if k in indicators
        ]
        if osc_parts:
            lines.append(f"  Oscillators: {'  '.join(osc_parts)}")

        ma_keys = [
            "EMA5", "SMA5", "EMA10", "SMA10", "EMA20", "SMA20",
            "EMA30", "SMA30", "EMA50", "SMA50", "EMA100", "SMA100",
            "EMA200", "SMA200", "VWMA", "HullMA9",
        ]
        ma_parts = [
            f"{k}={_format_value(indicators[k])}"
            for k in ma_keys
            if k in indicators
        ]
        if ma_parts:
            lines.append(f"  Moving Averages: {'  '.join(ma_parts)}")

        band_keys = ["BB.lower", "BB.upper", "P.SAR"]
        band_parts = [
            f"{k}={_format_value(indicators[k])}"
            for k in band_keys
            if k in indicators
        ]
        if band_parts:
            lines.append(f"  Bands: {'  '.join(band_parts)}")

        lines.extend(_format_pivot_table(indicators))

    return "\n".join(lines)


@tool
def get_tradingview_ta(
    symbol: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
) -> str:
    """Retrieve TradingView's aggregated technical analysis for a ticker.

    Uses the daily interval and returns the overall recommendation plus the
    oscillator and moving-average vote breakdown.  Key raw indicator values
    (RSI, MACD, moving averages, Bollinger Bands, pivot points, etc.) are
    also included so the analyst can reason about magnitude, not just vote
    direction.  Pivot levels for Classic, Fibonacci, Camarilla, Woodie and
    Demark methods are shown in a dedicated table.  Results are cached in
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
