"""yfinance-backed data tools for the MCP server."""

from __future__ import annotations

import json
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


def download_stock_data(
    tickers: str,
    period: str = "1mo",
    interval: str = "1d",
    start: str | None = None,
    end: str | None = None,
    auto_adjust: bool = True,
    multi_level_index: bool = False,
) -> str:
    """Batch-download historical OHLCV data via yf.download().

    This mirrors the yfinance ``download()`` API used by TradingAgents'
    stockstats_utils. Supports comma-separated tickers for batch fetch.

    Args:
        tickers: Comma-separated symbols, e.g. "AAPL,MSFT" or "600519.SS".
        period: yfinance period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max).
        interval: yfinance interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo).
        start: Optional start date (YYYY-MM-DD). Overrides period if both provided.
        end: Optional end date (YYYY-MM-DD).
        auto_adjust: Adjust OHLC for splits/dividends (default True).
        multi_level_index: Return multi-index DataFrame (default False).
    """
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        return "No tickers provided."

    kwargs: dict[str, Any] = {
        "tickers": " ".join(ticker_list),
        "interval": interval,
        "auto_adjust": auto_adjust,
        "multi_level_index": multi_level_index,
        "progress": False,
    }
    if start and end:
        kwargs["start"] = start
        kwargs["end"] = end
    else:
        kwargs["period"] = period

    df = yf.download(**kwargs)
    if df is None or df.empty:
        return f"No data returned for {ticker_list}."

    # Normalize multi-ticker column layout to records.
    df = df.reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    records = []
    for _, row in df.iterrows():
        record = {"date": str(row[date_col])}
        # For single ticker without multi_level_index, columns are Open/High/Low/Close/Adj Close/Volume.
        # For multiple tickers, columns are a MultiIndex like (Close, AAPL).
        for col in df.columns:
            if col == date_col:
                continue
            key = " ".join(str(c) for c in col) if isinstance(col, tuple) else str(col)
            try:
                value = float(row[col]) if col in df.columns else None
            except (ValueError, TypeError):
                value = str(row[col])
            record[key] = value
        records.append(record)

    return _json_dumps({"tickers": ticker_list, "count": len(records), "data": records})


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


def get_financials(ticker: str, statement: str = "income", freq: str = "annual") -> str:
    """Return financial statements for a ticker.

    Args:
        statement: One of 'income', 'balance', 'cash'.
        freq: 'annual' or 'quarterly'.
    """
    ticker = ticker.strip().upper()
    stock = yf.Ticker(ticker)

    quarterly = freq.lower() == "quarterly"
    if statement == "income":
        df = stock.quarterly_income_stmt if quarterly else stock.income_stmt
    elif statement == "balance":
        df = stock.quarterly_balance_sheet if quarterly else stock.balance_sheet
    elif statement == "cash":
        df = stock.quarterly_cashflow if quarterly else stock.cashflow
    else:
        return f"Unknown statement type: {statement}. Use 'income', 'balance', or 'cash'."

    if df is None or df.empty:
        return f"No {statement} statement data for {ticker}."

    records = []
    for col in df.columns:
        row = {"date": col.isoformat() if hasattr(col, "isoformat") else str(col)}
        row.update({idx: str(val) for idx, val in df[col].items()})
        records.append(row)
    return _json_dumps({"ticker": ticker, "statement": statement, "freq": freq, "data": records})


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


def get_news(ticker: str, count: int = 20) -> str:
    """Return recent news articles for a ticker.

    Args:
        ticker: Stock symbol, e.g. AAPL.
        count: Maximum number of articles to retrieve (default 20).
    """
    ticker = ticker.strip().upper()
    stock = yf.Ticker(ticker)
    news = stock.get_news(count=count)
    if not news:
        return f"No news for {ticker}."
    return _json_dumps({"ticker": ticker, "count": len(news), "news": news})


def search_news(query: str, count: int = 10) -> str:
    """Return news articles from a fuzzy yfinance Search query.

    Args:
        query: Search query, e.g. "Federal Reserve interest rates".
        count: Maximum number of articles to retrieve (default 10).
    """
    search = yf.Search(query, news_count=count, enable_fuzzy_query=True)
    news = search.news or []
    return _json_dumps({"query": query, "count": len(news), "news": news})


def get_insider_transactions(ticker: str) -> str:
    """Return insider transaction data for a ticker."""
    ticker = ticker.strip().upper()
    stock = yf.Ticker(ticker)
    data = stock.insider_transactions
    if data is None or data.empty:
        return f"No insider transactions for {ticker}."

    records = []
    for idx, row in data.iterrows():
        record = {"index": idx.isoformat() if hasattr(idx, "isoformat") else str(idx)}
        record.update({k: str(v) for k, v in row.items()})
        records.append(record)
    return _json_dumps({"ticker": ticker, "data": records})
