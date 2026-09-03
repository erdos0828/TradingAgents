"""Same-day OHLCV cache must not serve a stale snapshot all day (#1150).

The cache is keyed per symbol, so a run started before the day's bar was final
would be reused by every later run, feeding a stale close into technical
analysis. Two cases matter for a current-day request: the bar may be missing, or
present but still in progress (Yahoo publishes a partial daily candle intraday).
Refresh is bounded by a TTL so repeated runs cannot hammer the vendor.
"""
from __future__ import annotations

import time

import pandas as pd
import pytest

import tradingagents.dataflows.sqlite_cache as sqlite_cache
import tradingagents.dataflows.stockstats_utils as su

TODAY = pd.Timestamp("2026-07-18")
STALE = su.OHLCV_CACHE_TTL_SECONDS + 60


def _seed(symbol: str, tmp_path, monkeypatch, age_seconds=0.0, last_date="2026-07-17"):
    """Pre-seed the SQLite cache for ``symbol`` and return the refresh timestamp."""
    _patch_config(tmp_path, monkeypatch)
    sqlite_cache.store_ohlcv(
        symbol,
        pd.DataFrame({"Date": [last_date], "Close": [1.0]}),
    )
    refresh_ts = time.time() - age_seconds
    sqlite_cache.set_last_refresh(symbol, refresh_ts)
    return refresh_ts


def _patch_config(tmp_path, monkeypatch):
    """Route both stockstats_utils and sqlite_cache to the test cache dir."""
    cfg = {"data_cache_dir": str(tmp_path)}
    monkeypatch.setattr(su, "get_config", lambda: cfg)
    monkeypatch.setattr(sqlite_cache, "get_config", lambda: cfg)


@pytest.mark.unit
def test_current_day_cache_past_ttl_is_refreshed(tmp_path, monkeypatch):
    # Bar missing (rows stop at yesterday) and refresh older than the TTL -> refetch.
    ts = _seed("AAPL", tmp_path, monkeypatch, age_seconds=STALE)
    assert su._needs_same_day_refresh(ts, TODAY, TODAY) is True


@pytest.mark.unit
def test_partial_current_day_bar_is_still_refreshed(tmp_path, monkeypatch):
    # Today's row is present but may be an in-progress candle whose Close is not
    # the closing price. Row inspection can't distinguish it, so the TTL governs.
    ts = _seed("AAPL", tmp_path, monkeypatch, age_seconds=STALE, last_date="2026-07-18")
    assert su._needs_same_day_refresh(ts, TODAY, TODAY) is True


@pytest.mark.unit
def test_recent_cache_is_not_refetched(tmp_path, monkeypatch):
    # Written moments ago: don't hammer the vendor (weekend/holiday guard).
    ts = _seed("AAPL", tmp_path, monkeypatch)
    assert su._needs_same_day_refresh(ts, TODAY, TODAY) is False


@pytest.mark.unit
def test_historical_request_always_uses_cache(tmp_path, monkeypatch):
    # Past dates are immutable: never refetch, however old the cache is.
    past = pd.Timestamp("2026-05-01")
    ts = _seed("AAPL", tmp_path, monkeypatch, age_seconds=STALE, last_date="2026-04-30")
    assert su._needs_same_day_refresh(ts, past, TODAY) is False


@pytest.mark.unit
def test_load_ohlcv_refetches_stale_same_day_cache(tmp_path, monkeypatch):
    """End-to-end: the helper is actually wired into load_ohlcv's cache branch.

    Without this, the unit tests above would still pass if the helper were never
    called from the real code path.
    """
    _patch_config(tmp_path, monkeypatch)
    monkeypatch.setattr(su.pd.Timestamp, "today", staticmethod(lambda: TODAY))

    # Pre-seed the SQLite cache load_ohlcv will look for, aged past the TTL.
    _seed("AAPL", tmp_path, monkeypatch, age_seconds=STALE, last_date="2026-07-17")

    calls = []

    def _fake_download(*a, **k):
        calls.append(1)
        return pd.DataFrame(
            {"Date": pd.to_datetime(["2026-07-17", "2026-07-18"]), "Close": [100.0, 222.0]}
        ).set_index("Date")

    monkeypatch.setattr(su.yf, "download", _fake_download)

    out = su.load_ohlcv("AAPL", TODAY.strftime("%Y-%m-%d"))

    assert calls, "stale same-day cache must trigger a refetch"
    assert 222.0 in out["Close"].values, "refreshed close must reach the caller"


@pytest.mark.unit
def test_load_ohlcv_reuses_fresh_same_day_cache(tmp_path, monkeypatch):
    # Mirror image: a fresh cache must NOT trigger a download.
    _patch_config(tmp_path, monkeypatch)
    monkeypatch.setattr(su.pd.Timestamp, "today", staticmethod(lambda: TODAY))

    _seed("AAPL", tmp_path, monkeypatch, age_seconds=0.0, last_date="2026-07-18")

    def _fail_download(*a, **k):
        raise AssertionError("fresh cache must not refetch")

    monkeypatch.setattr(su.yf, "download", _fail_download)
    su.load_ohlcv("AAPL", TODAY.strftime("%Y-%m-%d"))
