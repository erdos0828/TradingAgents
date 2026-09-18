"""A-share routing: Chinese tickers use akshare, US tickers keep existing vendors."""
import copy
import unittest
from unittest import mock

import pytest

import tradingagents.dataflows.config as config_module
import tradingagents.default_config as default_config
from tradingagents.dataflows import interface
from tradingagents.dataflows.config import set_config


def _reset_config():
    config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)
    config_module._config["cache_tool_responses"] = False


@pytest.mark.unit
class AkshareRoutingTests(unittest.TestCase):
    def setUp(self):
        _reset_config()

    def tearDown(self):
        _reset_config()

    def _route_method(self, method, vendors):
        return mock.patch.dict(interface.VENDOR_METHODS, {method: vendors}, clear=False)

    def test_a_share_get_news_routes_to_akshare(self):
        set_config({"analysis_ticker": "600006.SS"})
        ak = mock.Mock(return_value="AK_NEWS")
        yf = mock.Mock(return_value="YF_NEWS")
        with self._route_method("get_news", {"akshare": ak, "yfinance": yf}):
            result = interface.route_to_vendor("get_news", "600006.SS", "2026-01-01", "2026-01-31")
        self.assertEqual(result, "AK_NEWS")
        ak.assert_called_once()
        yf.assert_not_called()

    def test_a_share_get_macro_routes_to_akshare(self):
        set_config({"analysis_ticker": "600006.SS"})
        ak = mock.Mock(return_value="AK_MACRO")
        fred = mock.Mock(return_value="FRED_MACRO")
        with self._route_method("get_macro_indicators", {"akshare": ak, "fred": fred}):
            result = interface.route_to_vendor("get_macro_indicators", "cpi", "2026-01-01")
        self.assertEqual(result, "AK_MACRO")
        ak.assert_called_once()
        fred.assert_not_called()

    def test_a_share_get_global_news_routes_to_akshare(self):
        set_config({"analysis_ticker": "000001.SZ"})
        ak = mock.Mock(return_value="AK_GLOBAL")
        yf = mock.Mock(return_value="YF_GLOBAL")
        with self._route_method("get_global_news", {"akshare": ak, "yfinance": yf}):
            result = interface.route_to_vendor("get_global_news", "2026-01-01", 7, 10)
        self.assertEqual(result, "AK_GLOBAL")
        ak.assert_called_once()
        yf.assert_not_called()

    def test_us_stock_keeps_yfinance(self):
        set_config({"analysis_ticker": "AAPL"})
        ak = mock.Mock(return_value="AK_NEWS")
        yf = mock.Mock(return_value="YF_NEWS")
        with self._route_method("get_news", {"akshare": ak, "yfinance": yf}):
            result = interface.route_to_vendor("get_news", "AAPL", "2026-01-01", "2026-01-31")
        self.assertEqual(result, "YF_NEWS")
        yf.assert_called_once()
        ak.assert_not_called()

    def test_us_stock_keeps_fred(self):
        set_config({"analysis_ticker": "TSLA"})
        ak = mock.Mock(return_value="AK_MACRO")
        fred = mock.Mock(return_value="FRED_MACRO")
        with self._route_method("get_macro_indicators", {"akshare": ak, "fred": fred}):
            result = interface.route_to_vendor("get_macro_indicators", "cpi", "2026-01-01")
        self.assertEqual(result, "FRED_MACRO")
        fred.assert_called_once()
        ak.assert_not_called()

    def test_bare_six_digit_code_is_a_share(self):
        set_config({"analysis_ticker": "600006"})
        ak = mock.Mock(return_value="AK_NEWS")
        with self._route_method("get_news", {"akshare": ak, "yfinance": mock.Mock()}):
            result = interface.route_to_vendor("get_news", "600006", "2026-01-01", "2026-01-31")
        self.assertEqual(result, "AK_NEWS")
        ak.assert_called_once()

    def test_non_a_share_ticker_stays_with_existing_vendor(self):
        for ticker in ("AAPL", "MSFT", "TSLA", "BABA", "9988.HK"):
            _reset_config()
            set_config({"analysis_ticker": ticker})
            ak = mock.Mock(return_value="AK_NEWS")
            yf = mock.Mock(return_value="YF_NEWS")
            with self._route_method("get_news", {"akshare": ak, "yfinance": yf}):
                result = interface.route_to_vendor(
                    "get_news", ticker, "2026-01-01", "2026-01-31"
                )
            self.assertEqual(result, "YF_NEWS", f"{ticker} should not route to akshare")
            yf.assert_called_once()
            ak.assert_not_called()


if __name__ == "__main__":
    unittest.main()
