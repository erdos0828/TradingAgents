"""Tool-response cache: routed vendor responses must be cached and reused.

Covers: identical calls served from the SQLite cache without re-invoking the
vendor, TTL expiry triggering a refetch, failure sentinels never being cached,
disabled config bypassing the cache, OHLCV-backed categories never being
intercepted, and the vendor chain participating in the cache key so a config
change cannot serve an unchosen vendor's cached data.
"""
import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

import tradingagents.dataflows.config as config_module
import tradingagents.default_config as default_config
from tradingagents.dataflows import interface, tool_response_cache
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.symbol_utils import NoMarketDataError


def _reset_config():
    # Hard reset: set_config() merges, so replace the global outright (same
    # approach as test_vendor_routing).
    config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)


def _no_data(symbol, *a, **k):
    raise NoMarketDataError(symbol, symbol, "no rows")


def _raises(exc):
    def impl(*a, **k):
        raise exc
    return impl


@pytest.mark.unit
class ToolResponseCacheTests(unittest.TestCase):
    def setUp(self):
        _reset_config()
        # Re-enable the cache (conftest disables it for unit tests by default)
        # and point the cache DB at a per-test temp directory.
        self._tmp = tempfile.TemporaryDirectory()
        config_module._config["cache_tool_responses"] = True
        config_module._config["data_cache_dir"] = self._tmp.name
        set_config({
            "data_vendors": {"news_data": "yfinance"},
            "analysis_ticker": "AAPL",
            "analysis_date": "2026-01-31",
        })

    def tearDown(self):
        self._tmp.cleanup()
        _reset_config()

    def _patch_news(self, vendor):
        return mock.patch.dict(
            interface.VENDOR_METHODS, {"get_news": {"yfinance": vendor}}, clear=False
        )

    def _db_path(self) -> Path:
        return Path(self._tmp.name) / "tradingagents_cache.db"

    def _cached_row(self, tool: str):
        conn = sqlite3.connect(str(self._db_path()))
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(
                "SELECT ticker, date, tool, params_hash, response "
                "FROM tool_response_cache WHERE tool = ?",
                (tool,),
            ).fetchone()
        finally:
            conn.close()

    def test_second_identical_call_served_from_cache(self):
        vendor = mock.Mock(return_value="NEWS_DATA")
        with self._patch_news(vendor):
            first = interface.route_to_vendor(
                "get_news", "AAPL", "2026-01-01", "2026-01-31"
            )
            second = interface.route_to_vendor(
                "get_news", "AAPL", "2026-01-01", "2026-01-31"
            )
        self.assertEqual(first, "NEWS_DATA")
        self.assertEqual(second, "NEWS_DATA")
        vendor.assert_called_once()  # second call hit the cache, not the vendor
        row = self._cached_row("get_news")
        self.assertEqual(row["ticker"], "AAPL")
        self.assertEqual(row["date"], "2026-01-31")

    def test_different_args_are_cached_separately(self):
        vendor = mock.Mock(side_effect=lambda t, s, e: f"NEWS:{t}")
        with self._patch_news(vendor):
            a = interface.route_to_vendor("get_news", "AAPL", "2026-01-01", "2026-01-31")
            b = interface.route_to_vendor("get_news", "MSFT", "2026-01-01", "2026-01-31")
            # Repeat the first call — must still hit its own cache entry.
            a2 = interface.route_to_vendor("get_news", "AAPL", "2026-01-01", "2026-01-31")
        self.assertEqual(a, "NEWS:AAPL")
        self.assertEqual(b, "NEWS:MSFT")
        self.assertEqual(a2, "NEWS:AAPL")
        self.assertEqual(vendor.call_count, 2)

    def test_ttl_expiry_refetches_from_vendor(self):
        vendor = mock.Mock(return_value="FRESH_NEWS")
        with self._patch_news(vendor):
            interface.route_to_vendor("get_news", "AAPL", "2026-01-01", "2026-01-31")
            # Age the cached row beyond any configured TTL.
            conn = sqlite3.connect(str(self._db_path()))
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("UPDATE tool_response_cache SET created_at = 0")
                conn.commit()
            finally:
                conn.close()
            result = interface.route_to_vendor(
                "get_news", "AAPL", "2026-01-01", "2026-01-31"
            )
        self.assertEqual(result, "FRESH_NEWS")
        self.assertEqual(vendor.call_count, 2)

    def test_no_data_sentinel_is_never_cached(self):
        vendor = mock.Mock(side_effect=_no_data)
        with self._patch_news(vendor):
            first = interface.route_to_vendor(
                "get_news", "FAKE", "2026-01-01", "2026-01-31"
            )
            second = interface.route_to_vendor(
                "get_news", "FAKE", "2026-01-01", "2026-01-31"
            )
        self.assertTrue(first.startswith("NO_DATA_AVAILABLE"))
        self.assertTrue(second.startswith("NO_DATA_AVAILABLE"))
        # A network/no-data blip must not be pinned: both calls re-attempted.
        self.assertEqual(vendor.call_count, 2)

    def test_optional_category_sentinel_is_never_cached(self):
        set_config({"data_vendors": {"macro_data": "fred"}})
        vendor = mock.Mock(side_effect=_raises(ValueError("FRED 400")))
        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_macro_indicators": {"fred": vendor}},
            clear=False,
        ):
            first = interface.route_to_vendor("get_macro_indicators", "cpi", "2026-01-01")
            second = interface.route_to_vendor("get_macro_indicators", "cpi", "2026-01-01")
        self.assertTrue(first.startswith("DATA_UNAVAILABLE"))
        self.assertTrue(second.startswith("DATA_UNAVAILABLE"))
        self.assertEqual(vendor.call_count, 2)

    def test_disabled_cache_bypasses_vendor_cache(self):
        set_config({"cache_tool_responses": False})
        vendor = mock.Mock(return_value="NEWS_DATA")
        with self._patch_news(vendor):
            interface.route_to_vendor("get_news", "AAPL", "2026-01-01", "2026-01-31")
            interface.route_to_vendor("get_news", "AAPL", "2026-01-01", "2026-01-31")
        self.assertEqual(vendor.call_count, 2)

    def test_ohlcv_backed_tools_are_not_intercepted(self):
        # get_stock_data keeps its dedicated freshness-aware OHLCV cache;
        # the generic response cache must never sit in front of it.
        set_config({"data_vendors": {"core_stock_apis": "yfinance"}})
        vendor = mock.Mock(return_value="OHLCV_DATA")
        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_stock_data": {"yfinance": vendor}},
            clear=False,
        ):
            interface.route_to_vendor("get_stock_data", "AAPL", "2026-01-01", "2026-01-31")
            interface.route_to_vendor("get_stock_data", "AAPL", "2026-01-01", "2026-01-31")
        self.assertEqual(vendor.call_count, 2)
        # And nothing was written for it into the response cache table. The
        # table is created lazily on the first cached call, so touch it first
        # (cache_stats opens/creates the schema) before asserting emptiness.
        tool_response_cache.cache_stats()
        conn = sqlite3.connect(str(self._db_path()))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT COUNT(*) FROM tool_response_cache WHERE tool = 'get_stock_data'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(rows, 0)

    def test_vendor_chain_change_invalidates_cache(self):
        # The vendor chain participates in the cache key: switching the
        # configured vendor must not serve the previous vendor's cached data.
        yf = mock.Mock(return_value="YF_NEWS")
        av = mock.Mock(return_value="AV_NEWS")
        set_config({"data_vendors": {"news_data": "yfinance"}})
        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_news": {"yfinance": yf, "alpha_vantage": av}},
            clear=False,
        ):
            first = interface.route_to_vendor(
                "get_news", "AAPL", "2026-01-01", "2026-01-31"
            )
            set_config({"data_vendors": {"news_data": "alpha_vantage"}})
            second = interface.route_to_vendor(
                "get_news", "AAPL", "2026-01-01", "2026-01-31"
            )
        self.assertEqual(first, "YF_NEWS")
        self.assertEqual(second, "AV_NEWS")
        yf.assert_called_once()
        av.assert_called_once()

    def test_cached_result_matches_first_vendor_response(self):
        # What is returned from the cache is byte-identical to the stored
        # vendor response (no re-formatting, no truncation).
        payload = "Some long news markdown\n" * 50
        vendor = mock.Mock(return_value=payload)
        with self._patch_news(vendor):
            interface.route_to_vendor("get_news", "AAPL", "2026-01-01", "2026-01-31")
            again = interface.route_to_vendor(
                "get_news", "AAPL", "2026-01-01", "2026-01-31"
            )
        self.assertEqual(again, payload)
        row = self._cached_row("get_news")
        self.assertEqual(row["ticker"], "AAPL")
        self.assertEqual(row["date"], "2026-01-31")

    def test_kwargs_participate_in_cache_key(self):
        # get_global_news routes (curr_date, look_back_days, limit); different
        # explicit limits must not share one cache entry. The tool has no ticker
        # argument, but the analysis context ticker/date are recorded.
        set_config({"data_vendors": {"news_data": "yfinance"}})
        vendor = mock.Mock(side_effect=lambda d, lb, lim: f"GLOBAL:{lb}:{lim}")
        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_global_news": {"yfinance": vendor}},
            clear=False,
        ):
            a = interface.route_to_vendor("get_global_news", "2026-01-01", 7, 10)
            b = interface.route_to_vendor("get_global_news", "2026-01-01", 7, 20)
            a2 = interface.route_to_vendor("get_global_news", "2026-01-01", 7, 10)
        self.assertEqual(a, "GLOBAL:7:10")
        self.assertEqual(b, "GLOBAL:7:20")
        self.assertEqual(a2, "GLOBAL:7:10")
        self.assertEqual(vendor.call_count, 2)
        conn = sqlite3.connect(str(self._db_path()))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT ticker, date, response FROM tool_response_cache "
                "WHERE tool = 'get_global_news'"
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual(len(rows), 2)  # a and b; a2 hit the cache
        for row in rows:
            self.assertEqual(row["ticker"], "AAPL")
            self.assertEqual(row["date"], "2026-01-31")

    def test_macro_tool_records_analysis_context(self):
        # get_macro_indicators has no ticker/date arguments, so it records the
        # current analysis context instead.
        set_config({
            "data_vendors": {"macro_data": "fred"},
            "analysis_ticker": "AAPL",
            "analysis_date": "2026-06-01",
        })
        vendor = mock.Mock(return_value="MACRO_DATA")
        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_macro_indicators": {"fred": vendor}},
            clear=False,
        ):
            interface.route_to_vendor("get_macro_indicators", "cpi", "2026-06-01", 365)
        row = self._cached_row("get_macro_indicators")
        self.assertEqual(row["ticker"], "AAPL")
        self.assertEqual(row["date"], "2026-06-01")

    def test_legacy_table_without_ticker_date_is_migrated(self):
        # An old cache DB that predates the ticker/date columns must be
        # rebuilt transparently; existing rows survive with NULL ticker/date.
        db = self._db_path()
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                """
                CREATE TABLE tool_response_cache (
                    tool TEXT NOT NULL,
                    params_hash TEXT NOT NULL,
                    params TEXT,
                    response TEXT NOT NULL,
                    cache_version INTEGER DEFAULT 1,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (tool, params_hash)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO tool_response_cache
                    (tool, params_hash, response, created_at)
                VALUES ('get_news', 'deadbeef', 'OLD_NEWS', 0)
                """
            )
            conn.commit()
        finally:
            conn.close()

        # First access triggers migration and recreates indexes.
        tool_response_cache.cache_stats()

        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        try:
            columns = {
                r["name"] for r in conn.execute("PRAGMA table_info(tool_response_cache)")
            }
            row = conn.execute(
                "SELECT ticker, date, response FROM tool_response_cache WHERE tool='get_news'"
            ).fetchone()
            indexes = {
                r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            }
        finally:
            conn.close()
        self.assertIn("ticker", columns)
        self.assertIn("date", columns)
        self.assertIsNone(row["ticker"])
        self.assertIsNone(row["date"])
        self.assertEqual(row["response"], "OLD_NEWS")
        self.assertIn("idx_tool_response_cache_ticker_date", indexes)
        self.assertIn("idx_tool_response_cache_tool", indexes)


if __name__ == "__main__":
    unittest.main()
