"""StockTwits fetch: transport-error resilience (#1024) and crypto symbol
mapping (#1113).

StockTwits lists crypto under ``<BASE>.X`` (Yahoo's ``BTC-USD`` 404s), and any
transport error must degrade to a placeholder rather than raise.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import requests

from tradingagents.dataflows import stocktwits


def _raise(exc):
    """Side-effect factory: returns a callable that raises ``exc``."""
    def _side_effect(*a, **kw):
        raise exc
    return _side_effect


@pytest.mark.unit
class TestStockTwitsResilience:
    @pytest.mark.parametrize(
        "exc",
        [
            requests.exceptions.ConnectionError("remote closed"),
            requests.exceptions.HTTPError("503 down"),
            requests.exceptions.Timeout("slow"),
            requests.exceptions.ProxyError("proxy down"),
            ValueError("malformed json"),  # json decoding failure branch
        ],
    )
    def test_transport_errors_return_placeholder(self, exc):
        with patch.object(stocktwits.requests, "get", side_effect=_raise(exc)):
            out = stocktwits.fetch_stocktwits_messages("NVDA")
        assert "unavailable" in out.lower()
        assert out.startswith("<stocktwits unavailable")


@pytest.mark.unit
class TestStockTwitsCryptoSymbols:
    @pytest.mark.parametrize(
        ("ticker", "expected"),
        [
            ("BTC-USD", "BTC.X"),
            ("eth-usd", "ETH.X"),
            ("SOL-USD", "SOL.X"),
            ("BTCUSD", "BTC.X"),      # undashed broker form
            ("BTC-USDT", "BTC.X"),    # stablecoin quote
            ("AMD", "AMD"),
            ("BRK-B", "BRK-B"),       # dashed class share: untouched
            ("GOLD", "GOLD"),         # real equity (aliases elsewhere): untouched here
            ("XYZ-USD", "XYZ-USD"),   # unknown base: not treated as crypto
        ],
    )
    def test_symbol_mapping(self, ticker, expected):
        assert stocktwits._stocktwits_symbol(ticker) == expected

    def test_crypto_pair_requests_dot_x_endpoint(self):
        seen = {}

        def fake_get(url, **kwargs):
            seen["url"] = url
            raise requests.exceptions.Timeout("stop after capturing the URL")

        with patch.object(stocktwits.requests, "get", side_effect=fake_get):
            stocktwits.fetch_stocktwits_messages("BTC-USD")
        assert "/symbol/BTC.X.json" in seen["url"]
