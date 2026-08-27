"""yfinance-backed data tools for the MCP server."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import yfinance as yf


def _json_dumps(obj: Any) -> str:
    """Dump an object to a compact JSON string, handling pandas timestamps."""

    def _default(o: Any) -> Any:
        if hasattr(o, "isoformat"):
            return o.isoformat()
        if hasattr(o, "item"):
            return o.item()
        return str(o)

    return json.dumps(obj, default=_default, ensure_ascii=False)


def get_stock_price(ticker: str) -> str:
    """Return the latest intraday price and trading session info for a ticker."""
    ticker = ticker.strip().upper()
    stock = yf.Ticker(ticker)
    hist = stock.history(period="2d", interval="1d")
    if hist.empty:
        return f"No price data available for {ticker}."

    latest = hist.iloc[-1]
    prev = hist.iloc[-2] if len(hist) > 1 else latest
    change = latest["Close"] - prev["Close"]
    change_pct = (change / prev["Close"] * 100) if prev["Close"] != 0 else 0.0

    result = {
        "ticker": ticker,
        "date": latest.name.isoformat() if hasattr(latest.name, "isoformat") else str(latest.name),
        "open": round(float(latest["Open"]), 4),
        "high": round(float(latest["High"]), 4),
        "low": round(float(latest["Low"]), 4),
        "close": round(float(latest["Close"]), 4),
        "volume": int(latest["Volume"]),
        "change": round(float(change), 4),
        "change_percent": round(float(change_pct), 4),
    }
    return _json_dumps(result)


def get_stock_history(
    ticker: str,
    period: str = "1mo",
    interval: str = "1d",
    start: str | None = None,
    end: str | None = None,
) -> str:
    """Return historical OHLCV data for a ticker.

    Args:
        ticker: Stock symbol, e.g. AAPL or 600519.SS.
        period: Valid yfinance period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max).
        interval: Valid yfinance interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo).
        start: Optional start date (YYYY-MM-DD). Overrides period if both provided.
        end: Optional end date (YYYY-MM-DD).
    """
    ticker = ticker.strip().upper()
    stock = yf.Ticker(ticker)

    kwargs: dict[str, Any] = {"interval": interval}
    if start and end:
        kwargs["start"] = start
        kwargs["end"] = end
    else:
        kwargs["period"] = period

    hist = stock.history(**kwargs)
    if hist.empty:
        return f"No historical data for {ticker} with period={period}, interval={interval}."

    records = []
    for idx, row in hist.iterrows():
        records.append(
            {
                "date": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]),
            }
        )
    return _json_dumps({"ticker": ticker, "count": len(records), "data": records})


def get_stock_info(ticker: str) -> str:
    """Return company/quote metadata for a ticker."""
    ticker = ticker.strip().upper()
    stock = yf.Ticker(ticker)
    info = stock.info or {}
    if not info:
        return f"No info available for {ticker}."

    keys = [
        "symbol",
        "shortName",
        "longName",
        "sector",
        "industry",
        "country",
        "currency",
        "exchange",
        "quoteType",
        "marketCap",
        "trailingPE",
        "forwardPE",
        "priceToBook",
        "dividendYield",
        "beta",
        "fiftyTwoWeekHigh",
        "fiftyTwoWeekLow",
        "fiftyDayAverage",
        "twoHundredDayAverage",
        "averageVolume",
        "website",
        "longBusinessSummary",
    ]
    result = {k: info.get(k) for k in keys if info.get(k) is not None}
    return _json_dumps(result)


def get_financials(ticker: str, statement: str = "income") -> str:
    """Return annual financial statements for a ticker.

    Args:
        statement: One of 'income', 'balance', 'cash'.
    """
    ticker = ticker.strip().upper()
    stock = yf.Ticker(ticker)

    if statement == "income":
        df = stock.financials
    elif statement == "balance":
        df = stock.balance_sheet
    elif statement == "cash":
        df = stock.cashflow
    else:
        return f"Unknown statement type: {statement}. Use 'income', 'balance', or 'cash'."

    if df is None or df.empty:
        return f"No {statement} statement data for {ticker}."

    records = []
    for col in df.columns:
        row = {"date": col.isoformat() if hasattr(col, "isoformat") else str(col)}
        row.update({idx: str(val) for idx, val in df[col].items()})
        records.append(row)
    return _json_dumps({"ticker": ticker, "statement": statement, "data": records})


def get_recommendations(ticker: str) -> str:
    """Return recent analyst recommendations for a ticker."""
    ticker = ticker.strip().upper()
    stock = yf.Ticker(ticker)
    recs = stock.recommendations
    if recs is None or recs.empty:
        return f"No recommendations for {ticker}."

    records = []
    for idx, row in recs.tail(20).iterrows():
        records.append(
            {
                "date": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                **{k: str(v) for k, v in row.items()},
            }
        )
    return _json_dumps({"ticker": ticker, "recommendations": records})


def search_tickers(query: str) -> str:
    """Search for tickers by company name or symbol."""
    result = yf.Search(query, max_results=10).news
    # yfinance Search.ticker does not expose quotes reliably, so use Ticker.info lookups
    # for common direct matches and fall back to search news.
    tickers = []
    for item in result or []:
        if "ticker" in item:
            tickers.append({"ticker": item["ticker"], "title": item.get("title", "")})
    return _json_dumps({"query": query, "matches": tickers})
