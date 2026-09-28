"""Tests for the stock snapshot screenshot generator."""

from unittest.mock import patch

import pandas as pd
import pytest

from tradingagents import chart_screenshot


@pytest.fixture
def sample_ohlcv():
    return pd.DataFrame({
        "Date": pd.to_datetime(["2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25"]),
        "Open": [100.0, 102.0, 101.0, 103.0, 104.0],
        "High": [103.0, 104.0, 104.0, 105.0, 106.0],
        "Low": [99.0, 100.0, 99.0, 102.0, 103.0],
        "Close": [102.0, 103.0, 103.5, 104.0, 105.5],
        "Volume": [10000, 12000, 11000, 13000, 14000],
    })


@pytest.mark.unit
def test_build_candlestick_svg_contains_candles_and_axis(sample_ohlcv):
    svg = chart_screenshot._build_candlestick_svg(sample_ohlcv, 600, 300)
    assert "<svg" in svg
    assert "</svg>" in svg
    # Each candle produces a wick line and a body rect; volume bars add more rects.
    assert svg.count("<line") >= 5
    assert svg.count("<rect") >= 5
    # Date labels are rendered for small counts.
    assert "09-21" in svg or "09-25" in svg
    # Right price axis labels should be present.
    assert "105.50" in svg or "99.00" in svg


@pytest.mark.unit
def test_build_candlestick_svg_draws_cost_line_and_trade_markers(sample_ohlcv):
    trades = {
        "2026-09-22": {
            "buy": {"qty": 100, "amount": 10200.0, "trades": []},
        },
        "2026-09-25": {
            "sell": {"qty": 50, "amount": 5275.0, "trades": []},
        },
    }
    svg = chart_screenshot._build_candlestick_svg(
        sample_ohlcv, 600, 300, cost_price=101.5, trades_by_date=trades
    )
    assert "成本 101.500" in svg
    assert ">B<" in svg
    assert ">S<" in svg


@pytest.mark.unit
def test_build_candlestick_svg_highlights_latest_close(sample_ohlcv):
    svg = chart_screenshot._build_candlestick_svg(sample_ohlcv, 600, 300)
    # Latest close (105.50) is highlighted on the right axis.
    assert "105.50" in svg
    assert 'fill="#3b82f6"' in svg


@pytest.mark.unit
def test_build_candlestick_svg_always_shows_cost_line(sample_ohlcv):
    # Cost price below the data range should still be visible.
    svg = chart_screenshot._build_candlestick_svg(
        sample_ohlcv, 600, 300, cost_price=80.0
    )
    assert "成本 80.000" in svg
    assert 'stroke-dasharray="6,4"' in svg


@pytest.mark.unit
def test_build_metrics_html_computes_pnl(sample_ohlcv):
    holding = {"name": "Test Inc", "quantity": 100.0, "cost_price": 100.0}
    trades = {}
    html = chart_screenshot._build_metrics_html(
        "AAPL", holding, sample_ohlcv, trades, "2026-09-25"
    )
    assert "Test Inc" in html
    assert "AAPL" in html
    # Latest close 105.5, prev 104.0, cost 100.0
    assert "10,550.00" in html  # market value
    assert "105.50" in html  # current price
    assert "550.00" in html  # position pnl
    assert "150.00" in html  # daily pnl


@pytest.mark.unit
def test_build_metrics_html_uses_a_share_currency(sample_ohlcv):
    holding = {"name": "东风", "quantity": 100.0, "cost_price": 7.0}
    html = chart_screenshot._build_metrics_html(
        "600006.SS", holding, sample_ohlcv, {}, "2026-09-25"
    )
    assert "¥" in html
    assert "$" not in html


@pytest.mark.unit
def test_generate_stock_screenshot_returns_path_when_successful(
    tmp_path, sample_ohlcv
):
    output = tmp_path / "AAPL_snapshot.png"
    with patch("tradingagents.chart_screenshot._html_to_png") as mock_png, patch(
        "tradingagents.chart_screenshot._get_price_history", return_value=sample_ohlcv
    ):
        mock_png.return_value = output
        result = chart_screenshot.generate_stock_screenshot(
            ticker="AAPL",
            analysis_date="2026-09-25",
            output_path=output,
            holding={"name": "Apple", "quantity": 100.0, "cost_price": 100.0},
        )

    assert result == output
    assert mock_png.called


@pytest.mark.unit
def test_generate_stock_screenshot_returns_none_on_playwright_failure(
    tmp_path, sample_ohlcv
):
    output = tmp_path / "AAPL_snapshot.png"
    with patch("tradingagents.chart_screenshot._html_to_png") as mock_png, patch(
        "tradingagents.chart_screenshot._get_price_history", return_value=sample_ohlcv
    ):
        mock_png.side_effect = RuntimeError("browser not installed")
        result = chart_screenshot.generate_stock_screenshot(
            ticker="AAPL",
            analysis_date="2026-09-25",
            output_path=output,
            holding={"name": "Apple", "quantity": 100.0, "cost_price": 100.0},
        )

    assert result is None
