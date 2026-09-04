"""SQLite cache for TradingView technical analysis consensus.

Shares the same on-disk database as the OHLCV cache but uses a dedicated
``tradingview_ta`` table keyed by (symbol, date).  One row per trading day
is stored; subsequent calls for the same symbol/date reuse the cached row.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from tradingagents.dataflows.sqlite_cache import _db_path
from tradingagents.dataflows.utils import safe_ticker_component

logger = logging.getLogger(__name__)

# Schema evolution: the ``indicators`` column was added after the initial
# release.  We create it on new databases and migrate existing tables via
# ALTER TABLE when the column is missing.
_INIT_SQL = """
CREATE TABLE IF NOT EXISTS tradingview_ta (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    recommendation TEXT,
    buy_votes INTEGER,
    sell_votes INTEGER,
    neutral_votes INTEGER,
    oscillators TEXT,
    moving_averages TEXT,
    indicators TEXT,
    cached_at REAL NOT NULL,
    PRIMARY KEY (symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_tradingview_ta_symbol_date
    ON tradingview_ta(symbol, date);
"""

_MIGRATE_ADD_INDICATORS = """
ALTER TABLE tradingview_ta ADD COLUMN indicators TEXT;
"""


def _normalize_symbol(symbol: str) -> str:
    """Return a safe symbol string suitable for DB keys."""
    return safe_ticker_component(symbol)


def _now_ts() -> float:
    """Return the current UTC timestamp as seconds since epoch."""
    return datetime.now(timezone.utc).timestamp()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the table and migrate older schemas that lack ``indicators``."""
    conn.executescript(_INIT_SQL)
    try:
        conn.execute(_MIGRATE_ADD_INDICATORS)
        conn.commit()
    except sqlite3.OperationalError:
        # Column already exists — safe to ignore.
        pass


def _get_connection() -> sqlite3.Connection:
    """Open a connection to the shared cache DB and ensure the TA table exists."""
    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_schema(conn)
    return conn


def load_ta(symbol: str, date: str) -> dict[str, Any] | None:
    """Return cached TA data for ``symbol`` on ``date`` if it exists."""
    norm = _normalize_symbol(symbol)
    try:
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM tradingview_ta WHERE symbol = ? AND date = ?",
                (norm, date),
            ).fetchone()
            if row:
                return {
                    "recommendation": row["recommendation"],
                    "buy_votes": row["buy_votes"],
                    "sell_votes": row["sell_votes"],
                    "neutral_votes": row["neutral_votes"],
                    "oscillators": json.loads(row["oscillators"] or "{}"),
                    "moving_averages": json.loads(row["moving_averages"] or "{}"),
                    "indicators": json.loads(row["indicators"] or "{}"),
                    "cached_at": row["cached_at"],
                }
    except Exception as exc:  # noqa: BLE001 — cache read failures are non-fatal
        logger.warning("Failed to load TradingView TA cache for %s %s: %s", symbol, date, exc)
    return None


def store_ta(symbol: str, date: str, data: dict[str, Any]) -> None:
    """Store (or replace) TA data for ``symbol`` on ``date``."""
    norm = _normalize_symbol(symbol)
    oscillators = json.dumps(data.get("oscillators", {}), ensure_ascii=False)
    moving_averages = json.dumps(data.get("moving_averages", {}), ensure_ascii=False)
    indicators = json.dumps(data.get("indicators", {}), ensure_ascii=False)
    try:
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO tradingview_ta (
                    symbol, date, recommendation, buy_votes, sell_votes, neutral_votes,
                    oscillators, moving_averages, indicators, cached_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    recommendation=excluded.recommendation,
                    buy_votes=excluded.buy_votes,
                    sell_votes=excluded.sell_votes,
                    neutral_votes=excluded.neutral_votes,
                    oscillators=excluded.oscillators,
                    moving_averages=excluded.moving_averages,
                    indicators=excluded.indicators,
                    cached_at=excluded.cached_at
                """,
                (
                    norm,
                    date,
                    data.get("recommendation"),
                    data.get("buy_votes"),
                    data.get("sell_votes"),
                    data.get("neutral_votes"),
                    oscillators,
                    moving_averages,
                    indicators,
                    _now_ts(),
                ),
            )
            conn.commit()
    except Exception as exc:  # noqa: BLE001 — cache write failures are non-fatal
        logger.warning("Failed to store TradingView TA cache for %s %s: %s", symbol, date, exc)
