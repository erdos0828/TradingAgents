"""Tests for the SQLite-backed OHLCV cache."""
from __future__ import annotations

import pandas as pd
import pytest

import tradingagents.dataflows.sqlite_cache as sqlite_cache


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """Route sqlite_cache to a temporary directory for each test."""
    config = {"data_cache_dir": str(tmp_path)}
    monkeypatch.setattr(sqlite_cache, "get_config", lambda: config)
    return config


@pytest.mark.unit
def test_store_and_load_ohlcv(cfg):
    symbol = "AAPL"
    df = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-16", "2026-07-17", "2026-07-18"]),
            "Open": [100.0, 101.0, 102.0],
            "High": [105.0, 106.0, 107.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [104.0, 105.0, 106.0],
            "Volume": [1_000_000, 1_100_000, 1_200_000],
        }
    )
    sqlite_cache.store_ohlcv(symbol, df)

    loaded = sqlite_cache.load_ohlcv(symbol)
    assert not loaded.empty
    assert list(loaded.columns) == ["Date", "Open", "High", "Low", "Close", "Volume", "Adj Close"]
    assert len(loaded) == 3
    assert loaded["Close"].iloc[-1] == 106.0


@pytest.mark.unit
def test_load_ohlcv_with_date_range(cfg):
    symbol = "AAPL"
    df = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-16", "2026-07-17", "2026-07-18"]),
            "Close": [100.0, 101.0, 102.0],
        }
    )
    sqlite_cache.store_ohlcv(symbol, df)

    loaded = sqlite_cache.load_ohlcv(symbol, start_date="2026-07-17", end_date="2026-07-17")
    assert len(loaded) == 1
    assert loaded["Close"].iloc[0] == 101.0


@pytest.mark.unit
def test_store_overwrites_existing_rows(cfg):
    symbol = "AAPL"
    df1 = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-18"]),
            "Close": [100.0],
        }
    )
    sqlite_cache.store_ohlcv(symbol, df1)

    df2 = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-18"]),
            "Close": [200.0],
        }
    )
    sqlite_cache.store_ohlcv(symbol, df2)

    loaded = sqlite_cache.load_ohlcv(symbol)
    assert len(loaded) == 1
    assert loaded["Close"].iloc[0] == 200.0


@pytest.mark.unit
def test_has_symbol_and_delete(cfg):
    symbol = "AAPL"
    assert not sqlite_cache.has_symbol(symbol)

    sqlite_cache.store_ohlcv(
        symbol,
        pd.DataFrame({"Date": pd.to_datetime(["2026-07-18"]), "Close": [100.0]}),
    )
    assert sqlite_cache.has_symbol(symbol)

    sqlite_cache.delete_symbol(symbol)
    assert not sqlite_cache.has_symbol(symbol)


@pytest.mark.unit
def test_last_refresh_tracking(cfg):
    symbol = "AAPL"
    assert sqlite_cache.get_last_refresh(symbol) is None

    sqlite_cache.set_last_refresh(symbol, 12345.0)
    assert sqlite_cache.get_last_refresh(symbol) == 12345.0


@pytest.mark.unit
def test_store_ignores_empty_dataframe(cfg):
    symbol = "AAPL"
    sqlite_cache.store_ohlcv(symbol, pd.DataFrame())
    assert not sqlite_cache.has_symbol(symbol)


@pytest.mark.unit
def test_store_normalizes_index_date_column(cfg):
    symbol = "AAPL"
    df = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [105.0],
            "Low": [99.0],
            "Close": [104.0],
            "Volume": [1_000_000],
        },
        index=pd.to_datetime(["2026-07-18"]),
    )
    sqlite_cache.store_ohlcv(symbol, df)

    loaded = sqlite_cache.load_ohlcv(symbol)
    assert len(loaded) == 1
    assert loaded["Date"].iloc[0].strftime("%Y-%m-%d") == "2026-07-18"


@pytest.mark.unit
def test_migrate_from_csv(cfg, tmp_path):
    symbol = "AAPL"
    csv_file = tmp_path / "AAPL-YFin-data-2021-07-18-2026-07-19.csv"
    pd.DataFrame(
        {
            "Date": ["2026-07-17", "2026-07-18"],
            "Open": [100.0, 101.0],
            "High": [105.0, 106.0],
            "Low": [99.0, 100.0],
            "Close": [104.0, 105.0],
            "Volume": [1_000_000, 1_100_000],
        }
    ).to_csv(csv_file, index=False)

    imported = sqlite_cache.migrate_from_csv(str(tmp_path))
    assert imported == 1

    loaded = sqlite_cache.load_ohlcv(symbol)
    assert len(loaded) == 2
    assert loaded["Close"].iloc[-1] == 105.0
