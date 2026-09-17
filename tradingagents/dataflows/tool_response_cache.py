"""SQLite cache for routed vendor tool responses.

Covers the tools whose vendor responses are plain strings (news, fundamentals,
macro, prediction markets) and have no dedicated cache of their own. Shares
the same on-disk database as the OHLCV cache but uses a dedicated
``tool_response_cache`` table keyed by (tool, params_hash). Each row also
records the ``ticker`` and ``date`` dimensions so the cache can be queried
and pruned by symbol and analysis date.

The OHLCV-backed tools (``get_stock_data`` / ``get_indicators``) are NOT
handled here: they keep their dedicated cache in ``stockstats_utils`` /
``sqlite_cache`` whose same-day freshness logic this generic layer must not
bypass.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tradingagents.dataflows.sqlite_cache import _db_path

logger = logging.getLogger(__name__)

# Bump when the cached payload semantics change (e.g. new fields), so old
# rows can be invalidated en masse by consumers.
CACHE_VERSION = 1

# Rows older than this are purged opportunistically during stores.
DEFAULT_MAX_AGE_SECONDS = 30 * 24 * 3600

# Purge check frequency: every N-th store triggers an expired-row sweep.
_PURGE_EVERY_N_STORES = 128

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS tool_response_cache (
    ticker TEXT,
    date TEXT,
    tool TEXT NOT NULL,
    params_hash TEXT NOT NULL,
    params TEXT,
    response TEXT NOT NULL,
    cache_version INTEGER DEFAULT 1,
    created_at REAL NOT NULL,
    PRIMARY KEY (tool, params_hash)
);

CREATE INDEX IF NOT EXISTS idx_tool_response_cache_ticker_date
    ON tool_response_cache(ticker, date);

CREATE INDEX IF NOT EXISTS idx_tool_response_cache_tool
    ON tool_response_cache(tool, params_hash);
"""

# Migration for the original schema (pre-ticker/date columns): rebuild the
# table so the new columns sit at the front of the schema as expected.
_MIGRATE_REBUILD_FOR_TICKER_DATE = """
CREATE TABLE IF NOT EXISTS _tool_response_cache_new (
    ticker TEXT,
    date TEXT,
    tool TEXT NOT NULL,
    params_hash TEXT NOT NULL,
    params TEXT,
    response TEXT NOT NULL,
    cache_version INTEGER DEFAULT 1,
    created_at REAL NOT NULL,
    PRIMARY KEY (tool, params_hash)
);

INSERT INTO _tool_response_cache_new
    (ticker, date, tool, params_hash, params, response, cache_version, created_at)
SELECT NULL, NULL, tool, params_hash, params, response, cache_version, created_at
FROM tool_response_cache;

DROP TABLE tool_response_cache;
ALTER TABLE _tool_response_cache_new RENAME TO tool_response_cache;
"""

_store_counter = itertools.count()


def _now_ts() -> float:
    """Return the current UTC timestamp as seconds since epoch."""
    return datetime.now(UTC).timestamp()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the table and rebuild legacy schemas that lack ticker/date."""
    cur = conn.execute("PRAGMA table_info(tool_response_cache)")
    columns = {row["name"] for row in cur.fetchall()}
    if not columns:
        # Fresh database: create the table and its indexes in one go.
        conn.executescript(_INIT_SQL)
    elif "ticker" not in columns or "date" not in columns:
        # Legacy schema predates the ticker/date columns. Rebuild the table
        # first, then create indexes on the new schema.
        conn.executescript(_MIGRATE_REBUILD_FOR_TICKER_DATE)
        conn.executescript(_INIT_SQL)
    conn.commit()


def _get_connection() -> sqlite3.Connection:
    """Open a connection to the shared cache DB and ensure the table exists."""
    db: Path = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_schema(conn)
    return conn


def build_params_key(
    method: str,
    args: tuple,
    kwargs: dict,
    vendor_chain: list[str],
) -> tuple[str, str]:
    """Return ``(params_hash, readable_repr)`` for a routed call.

    The vendor chain participates in the hash: identical arguments routed to
    a different vendor (after a ``data_vendors`` config change) must not be
    served the previous vendor's cached response.
    """
    payload = json.dumps(
        {
            "method": method,
            "args": list(args),
            "kwargs": dict(sorted(kwargs.items())),
            "vendors": list(vendor_chain),
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    params_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    parts = [repr(v) for v in args]
    parts.extend(f"{k}={v!r}" for k, v in sorted(kwargs.items()))
    return params_hash, ", ".join(parts)


def load_response(tool: str, params_hash: str, ttl_seconds: float) -> str | None:
    """Return the cached response for ``tool``/``params_hash`` if fresh.

    ``ttl_seconds`` is the category-specific freshness window; entries older
    than that are treated as absent so the caller re-fetches. Cache read
    failures are logged and non-fatal: a broken cache must never break the
    fetch path.
    """
    try:
        conn = _get_connection()
        try:
            row = conn.execute(
                "SELECT response, created_at FROM tool_response_cache "
                "WHERE tool = ? AND params_hash = ?",
                (tool, params_hash),
            ).fetchone()
        finally:
            conn.close()
        if row is not None and (_now_ts() - row["created_at"]) <= ttl_seconds:
            return row["response"]
    except Exception as exc:  # noqa: BLE001 — cache read failures are non-fatal
        logger.warning("Failed to load tool response cache for %s: %s", tool, exc)
    return None


def store_response(
    ticker: str | None,
    date: str | None,
    tool: str,
    params_hash: str,
    params: str,
    response: str,
) -> None:
    """Store (or replace) the response for a routed call.

    Failures are non-fatal for the same reason as ``load_response``.
    Opportunistically purges rows past ``DEFAULT_MAX_AGE_SECONDS`` every
    ``_PURGE_EVERY_N_STORES``-th call so the table does not grow unbounded
    across daily runs.
    """
    try:
        conn = _get_connection()
        try:
            conn.execute(
                """
                INSERT INTO tool_response_cache (
                    ticker, date, tool, params_hash, params, response, cache_version, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tool, params_hash) DO UPDATE SET
                    ticker=excluded.ticker,
                    date=excluded.date,
                    params=excluded.params,
                    response=excluded.response,
                    cache_version=excluded.cache_version,
                    created_at=excluded.created_at
                """,
                (
                    ticker,
                    date,
                    tool,
                    params_hash,
                    params,
                    response,
                    CACHE_VERSION,
                    _now_ts(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        if next(_store_counter) % _PURGE_EVERY_N_STORES == 0:
            purge_expired()
    except Exception as exc:  # noqa: BLE001 — cache write failures are non-fatal
        logger.warning("Failed to store tool response cache for %s: %s", tool, exc)


def purge_expired(max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS) -> int:
    """Delete rows older than ``max_age_seconds``; return the row count.

    Public so operators can sweep the cache from a maintenance script.
    """
    try:
        conn = _get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM tool_response_cache WHERE created_at < ?",
                (_now_ts() - max_age_seconds,),
            )
            conn.commit()
        finally:
            conn.close()
        if cursor.rowcount:
            logger.info(
                "Purged %d expired tool response cache rows (older than %.0fs)",
                cursor.rowcount, max_age_seconds,
            )
        return cursor.rowcount
    except Exception as exc:  # noqa: BLE001 — cache purge failures are non-fatal
        logger.warning("Failed to purge tool response cache: %s", exc)
        return 0


def cache_stats() -> dict[str, Any]:
    """Return a small summary of the cache table contents (for debugging)."""
    try:
        conn = _get_connection()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n, MIN(created_at) AS oldest, MAX(created_at) AS newest "
                "FROM tool_response_cache"
            ).fetchone()
        finally:
            conn.close()
        return {
            "rows": row["n"] if row else 0,
            "oldest": row["oldest"] if row else None,
            "newest": row["newest"] if row else None,
        }
    except Exception as exc:  # noqa: BLE001 — stats are best-effort
        logger.warning("Failed to read tool response cache stats: %s", exc)
        return {"rows": 0, "oldest": None, "newest": None}
