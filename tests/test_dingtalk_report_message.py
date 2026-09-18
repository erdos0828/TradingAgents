"""Tests for DingTalk report message formatting."""

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from cli.main import _build_dingtalk_report_message
from tradingagents.dataflows.config import set_config


@pytest.fixture
def sample_ohlcv():
    return pd.DataFrame({
        "Date": ["2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17"],
        "Open": [39.50, 40.00, 40.20, 40.50],
        "High": [40.00, 40.50, 40.80, 41.00],
        "Low": [39.00, 39.80, 40.00, 40.20],
        "Close": [39.80, 40.20, 40.50, 40.80],
        "Volume": [100000, 120000, 110000, 130000],
    })


def _write_holdings(tmp_path: Path, holdings: list[dict]) -> Path:
    path = tmp_path / "portfolio_holdings.json"
    path.write_text(json.dumps({"holdings": holdings}, ensure_ascii=False), encoding="utf-8")
    return path


def test_a_share_with_portfolio_name(sample_ohlcv, tmp_path):
    """A-share tickers show the portfolio name alongside the ticker."""
    holdings_path = _write_holdings(tmp_path, [{
        "ticker": "600006.SS",
        "name": "东风股份",
        "quantity": 42300,
        "cost_price": 7.2207,
    }])
    set_config({"portfolio_holdings_path": str(holdings_path), "project_dir": str(tmp_path)})

    save_path = tmp_path / "report"
    save_path.mkdir()

    with patch("cli.main.load_ohlcv", return_value=sample_ohlcv):
        title, body = _build_dingtalk_report_message(
            "600006.SS", "2026-09-17", save_path, {}
        )

    assert "东风股份（600006.SS）" in title
    assert "**最近数据：**" in body
    assert "| 日期 | 开盘 | 最高 | 最低 | 收盘 | 涨跌 |" in body
    # Three recent trading days are shown.
    assert body.count("2026-09-") >= 3
    # Holding PnL is rendered inside the recent-data section.
    assert body.index("**最近数据：**") < body.index("**持仓成本：**")
    assert body.index("**持仓成本：**") < body.index("**最终决策：**")
    assert "**总收益：**" in body


def test_recent_ohlcv_table_includes_change(sample_ohlcv, tmp_path):
    """Recent-data section shows open/high/low/close and day-on-day change."""
    holdings_path = _write_holdings(tmp_path, [{
        "ticker": "AAPL",
        "name": "Apple",
        "quantity": 100,
        "cost_price": 150.0,
    }])
    set_config({"portfolio_holdings_path": str(holdings_path), "project_dir": str(tmp_path)})
    save_path = tmp_path / "report"
    save_path.mkdir()

    with patch("cli.main.load_ohlcv", return_value=sample_ohlcv):
        _, body = _build_dingtalk_report_message(
            "AAPL", "2026-09-17", save_path, {"final_trade_decision": "Hold"}
        )

    # Change from 40.20 to 40.50 on 2026-09-16.
    assert "| 2026-09-16 | 40.20 | 40.80 | 40.00 | 40.50 | +0.75% |" in body
    # Change from 40.50 to 40.80 on 2026-09-17.
    assert "| 2026-09-17 | 40.50 | 41.00 | 40.20 | 40.80 | +0.74% |" in body


def test_holding_pnl_calculation(sample_ohlcv, tmp_path):
    """Holding PnL is computed from the latest close and portfolio cost price."""
    holdings_path = _write_holdings(tmp_path, [{
        "ticker": "600036.SS",
        "name": "招商银行",
        "quantity": 700,
        "cost_price": 35.1053,
    }])
    set_config({"portfolio_holdings_path": str(holdings_path), "project_dir": str(tmp_path)})
    save_path = tmp_path / "report"
    save_path.mkdir()

    with patch("cli.main.load_ohlcv", return_value=sample_ohlcv):
        _, body = _build_dingtalk_report_message("600036.SS", "2026-09-17", save_path, {})

    # Latest close is 40.80.
    total_cost = 700 * 35.1053  # 24573.71
    total_pnl = 700 * 40.80 - total_cost  # 3996.29
    pnl_pct = total_pnl / total_cost * 100
    assert f"**持仓成本：** {total_cost:,.2f}" in body
    assert f"**总收益：** {total_pnl:+.2f} ({pnl_pct:+.2f}%)" in body


def test_non_holding_ticker_uses_resolved_identity(sample_ohlcv, tmp_path):
    """Tickers not in the portfolio still get a resolved company name in the title."""
    set_config({"portfolio_holdings_path": str(tmp_path / "missing.json"), "project_dir": str(tmp_path)})
    save_path = tmp_path / "report"
    save_path.mkdir()

    with patch("cli.main.load_ohlcv", return_value=sample_ohlcv):
        with patch(
            "cli.main.resolve_instrument_identity",
            return_value={"company_name": "Tesla Inc"},
        ):
            title, body = _build_dingtalk_report_message(
                "TSLA", "2026-09-17", save_path, {}
            )

    assert "Tesla Inc（TSLA）" in title
    assert "**最近数据：**" in body
    # No holding section for a non-held ticker.
    assert "**持仓成本：**" not in body


def test_missing_ohlcv_gracefully(sample_ohlcv, tmp_path):
    """When OHLCV is unavailable the message still sends without the data section."""
    holdings_path = _write_holdings(tmp_path, [{
        "ticker": "MSFT",
        "name": "Microsoft",
        "quantity": 200,
        "cost_price": 463.917,
    }])
    set_config({"portfolio_holdings_path": str(holdings_path), "project_dir": str(tmp_path)})
    save_path = tmp_path / "report"
    save_path.mkdir()

    with patch("cli.main.load_ohlcv", return_value=None):
        title, body = _build_dingtalk_report_message("MSFT", "2026-09-17", save_path, {})

    assert "Microsoft（MSFT）" in title
    assert "**最近数据：**" not in body
    # No holding section when latest close is unknown.
    assert "**持仓成本：**" not in body
