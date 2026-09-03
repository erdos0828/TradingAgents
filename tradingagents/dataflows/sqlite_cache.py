"""SQLite-backed OHLCV cache for TradingAgents.

Replaces the per-symbol CSV files with a single SQLite database under the
configured ``data_cache_dir``. The schema stores one row per (symbol, date)
and keeps a per-symbol refresh timestamp for same-day TTL handling.

Existing CSV cache files can be imported once via ``migrate_from_csv``.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .config import get_config
from .utils import safe_ticker_component

logger = logging.getLogger(__name__)

DB_FILENAME = "tradingagents_cache.db"

# Map incoming DataFrame columns (from yfinance / CSV) to DB columns.
COLUMN_MAP = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
    # Also accept already-lowercased variants.
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "adj close": "adj_close",
    "adj_close": "adj_close",
    "volume": "volume",
}

DB_COLUMNS = ["open", "high", "low", "close", "volume", "adj_close"]


_INIT_SQL = """
CREATE TABLE IF NOT EXISTS ohlcv (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    adj_close REAL,
    cached_at REAL NOT NULL,
    PRIMARY KEY (symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_date
    ON ohlcv(symbol, date);

CREATE TABLE IF NOT EXISTS symbol_refresh (
    symbol TEXT PRIMARY KEY,
    refreshed_at REAL NOT NULL
);
"""


def _cache_dir() -> str:
    """Return the configured cache directory, creating it if needed."""
    cache_dir = get_config()["data_cache_dir"]
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _db_path() -> Path:
    """Return the path to the SQLite cache database."""
    return Path(_cache_dir()) / DB_FILENAME


def _normalize_symbol(symbol: str) -> str:
    """Return a safe symbol string suitable for DB keys."""
    return safe_ticker_component(symbol)


def _now_ts() -> float:
    """Return the current UTC timestamp as seconds since epoch."""
    return datetime.now(timezone.utc).timestamp()


def _to_date_str(value: Any) -> str | None:
    """Coerce a date-like value to ISO date string (YYYY-MM-DD)."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        # Already a string; validate it looks like a date.
        try:
            return pd.to_datetime(value).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return None
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def get_connection(create: bool = True) -> sqlite3.Connection:
    """Open a SQLite connection to the cache database.

    The connection has row factories enabled and creates required tables.
    Callers are responsible for closing the connection.

    When ``create`` is ``False`` and the database file does not yet exist,
    returns a transient in-memory connection so read-only checks can report
    "no data" without leaving an empty database file on disk.
    """
    db = _db_path()
    if not create and not db.exists():
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(_INIT_SQL)
        return conn
    conn = sqlite3.connect(str(db), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_INIT_SQL)
    conn.commit()
    return conn


def store_ohlcv(symbol: str, data: pd.DataFrame) -> None:
    """Store or replace OHLCV rows for ``symbol`` in the SQLite cache.

    The input DataFrame is expected to contain a date-like column named
    ``Date``, ``date``, or ``Datetime`` (or a DatetimeIndex). Price/volume
    columns are normalized to the DB schema.
    """
    if data is None or data.empty:
        return

    df = data.copy()

    # Normalize date column.
    if "Date" in df.columns:
        df["date"] = pd.to_datetime(df["Date"], errors="coerce")
    elif "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    elif "Datetime" in df.columns:
        df["date"] = pd.to_datetime(df["Datetime"], errors="coerce")
    elif isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
        df["date"] = pd.to_datetime(df["index"], errors="coerce")
    else:
        raise ValueError(f"Cannot locate date column for {symbol}")

    df = df.dropna(subset=["date"])
    if df.empty:
        return

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    # Normalize price/volume columns.
    db_values: dict[str, pd.Series] = {"symbol": pd.Series([_normalize_symbol(symbol)] * len(df))}
    for src_col, db_col in COLUMN_MAP.items():
        if src_col in df.columns and db_col not in db_values:
            db_values[db_col] = pd.to_numeric(df[src_col], errors="coerce")

    for col in DB_COLUMNS:
        if col not in db_values:
            db_values[col] = pd.Series([None] * len(df), dtype="float64")

    db_values["date"] = df["date"]
    db_values["cached_at"] = pd.Series([_now_ts()] * len(df))

    out_df = pd.DataFrame(db_values)
    out_df = out_df[["symbol", "date"] + DB_COLUMNS + ["cached_at"]]

    conn = get_connection()
    try:
        conn.executemany(
            """
            INSERT INTO ohlcv (symbol, date, open, high, low, close, volume, adj_close, cached_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, date) DO UPDATE SET
                open=excluded.open,
                high=excluded.high,
                low=excluded.low,
                close=excluded.close,
                volume=excluded.volume,
                adj_close=excluded.adj_close,
                cached_at=excluded.cached_at
            """,
            out_df.itertuples(index=False, name=None),
        )
        _set_refresh_ts(conn, symbol, _now_ts())
        conn.commit()
    finally:
        conn.close()


def load_ohlcv(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Load cached OHLCV rows for ``symbol`` as a DataFrame.

    Column names match yfinance output (``Date``, ``Open``, ``High``, ``Low``,
    ``Close``, ``Volume``, ``Adj Close``). Returns an empty DataFrame if no
    cached rows match.
    """
    norm = _normalize_symbol(symbol)
    conn = get_connection(create=False)
    try:
        query = "SELECT date, open, high, low, close, volume, adj_close FROM ohlcv WHERE symbol = ?"
        params: list[Any] = [norm]
        if start_date is not None:
            query += " AND date >= ?"
            params.append(_to_date_str(start_date))
        if end_date is not None:
            query += " AND date <= ?"
            params.append(_to_date_str(end_date))
        query += " ORDER BY date"

        df = pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.rename(
        columns={
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "adj_close": "Adj Close",
        }
    )
    return df


def has_symbol(symbol: str) -> bool:
    """Return True if any cached row exists for ``symbol``."""
    norm = _normalize_symbol(symbol)
    conn = get_connection(create=False)
    try:
        row = conn.execute(
            "SELECT 1 FROM ohlcv WHERE symbol = ? LIMIT 1", (norm,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_last_refresh(symbol: str) -> float | None:
    """Return the last refresh timestamp for ``symbol``, or None."""
    norm = _normalize_symbol(symbol)
    conn = get_connection(create=False)
    try:
        row = conn.execute(
            "SELECT refreshed_at FROM symbol_refresh WHERE symbol = ?", (norm,)
        ).fetchone()
        return row["refreshed_at"] if row else None
    finally:
        conn.close()


def set_last_refresh(symbol: str, timestamp: float | None = None) -> None:
    """Set the last refresh timestamp for ``symbol``."""
    ts = timestamp if timestamp is not None else _now_ts()
    conn = get_connection()
    try:
        _set_refresh_ts(conn, symbol, ts)
        conn.commit()
    finally:
        conn.close()


def _set_refresh_ts(conn: sqlite3.Connection, symbol: str, timestamp: float) -> None:
    """Internal helper: update refresh timestamp within an existing transaction."""
    norm = _normalize_symbol(symbol)
    conn.execute(
        """
        INSERT INTO symbol_refresh (symbol, refreshed_at)
        VALUES (?, ?)
        ON CONFLICT(symbol) DO UPDATE SET refreshed_at=excluded.refreshed_at
        """,
        (norm, timestamp),
    )


def delete_symbol(symbol: str) -> None:
    """Remove all cached OHLCV rows and refresh metadata for ``symbol``."""
    norm = _normalize_symbol(symbol)
    conn = get_connection()
    try:
        conn.execute("DELETE FROM ohlcv WHERE symbol = ?", (norm,))
        conn.execute("DELETE FROM symbol_refresh WHERE symbol = ?", (norm,))
        conn.commit()
    finally:
        conn.close()


def migrate_from_csv(cache_dir: str | None = None) -> int:
    """Import existing CSV cache files into the SQLite database.

    Returns the number of CSV files successfully imported.
    """
    if cache_dir is None:
        cache_dir = _cache_dir()

    cache_path = Path(cache_dir)
    if not cache_path.exists():
        return 0

    imported = 0
    for csv_file in cache_path.glob("*-YFin-data-*.csv"):
        try:
            df = pd.read_csv(csv_file, on_bad_lines="skip", encoding="utf-8")
            if df.empty or "Close" not in df.columns:
                continue

            # Infer symbol from filename: {symbol}-YFin-data-{start}-{end}.csv
            symbol = csv_file.stem.split("-YFin-data-")[0]
            if not symbol:
                continue

            store_ohlcv(symbol, df)
            imported += 1
            logger.info("Migrated cache CSV to SQLite: %s", csv_file.name)
        except Exception as exc:
            logger.warning("Failed to migrate %s: %s", csv_file.name, exc)

    return imported
