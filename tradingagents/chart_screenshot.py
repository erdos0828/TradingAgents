"""Generate a PNG screenshot of the per-stock "snapshot" card.

Used by the ``analyze`` command to attach a chart image to DingTalk
notifications.  The card is rendered as a self-contained HTML page (no
external CDN dependencies) and converted to PNG via Playwright.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import traceback
from contextlib import suppress
from pathlib import Path
from typing import Any

import pandas as pd

from tradingagents.dataflows import sqlite_cache
from tradingagents.dataflows.config import get_config, set_config

# Default output size matches a common landscape card suitable for chat clients.
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 675


def _currency_symbol(ticker: str) -> str:
    """Return ¥ for A-share tickers, $ otherwise."""
    upper = ticker.upper()
    if upper.endswith((".SS", ".SZ", ".BJ")):
        return "¥"
    return "$"


def _ensure_config_cache_dir() -> Path:
    """Return the configured cache directory, making sure config is loaded."""
    cache_dir = get_config().get("data_cache_dir", "cache")
    path = Path(cache_dir)
    if not path.is_absolute():
        path = Path(os.getcwd()) / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_portfolio_holding(ticker: str) -> dict[str, Any] | None:
    """Load a single holding from the portfolio holdings file."""
    config = get_config()
    holdings_path = config.get("portfolio_holdings_path") or os.path.join(
        "data", "portfolio_holdings.json"
    )
    path = Path(holdings_path)
    if not path.is_absolute():
        project_dir = config.get("project_dir", os.getcwd())
        path = Path(project_dir) / path

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for h in data.get("holdings", []):
            if h.get("ticker") == ticker:
                return {
                    "name": h.get("name", ticker),
                    "quantity": float(h.get("quantity", 0) or 0),
                    "cost_price": float(h.get("cost_price", 0) or 0),
                }
    except Exception:
        pass
    return None


def _load_transactions_by_ticker(ticker: str) -> list[dict[str, Any]]:
    """Load transaction records for a single ticker."""
    config = get_config()
    transactions_path = config.get("portfolio_transactions_path") or os.path.join(
        "data", "transactions", "transactions.json"
    )
    path = Path(transactions_path)
    if not path.is_absolute():
        project_dir = config.get("project_dir", os.getcwd())
        path = Path(project_dir) / path

    try:
        with open(path, encoding="utf-8") as f:
            records = json.load(f)
        return [r for r in records if r.get("ticker") == ticker]
    except Exception:
        return []


def _aggregate_trades(trades: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    """Aggregate trades by date and side. Returns {date: {side: {...}}}."""
    by_date: dict[str, dict[str, dict[str, Any]]] = {}
    for t in trades:
        date = t.get("date")
        side = t.get("side")
        if not date or side not in ("buy", "sell"):
            continue
        by_date.setdefault(date, {}).setdefault(
            side, {"qty": 0, "amount": 0.0, "trades": []}
        )
        entry = by_date[date][side]
        entry["qty"] += t.get("quantity", 0) or 0
        entry["amount"] += t.get("amount", 0.0) or 0.0
        entry["trades"].append(t)
    return by_date


def _get_price_history(
    ticker: str,
    analysis_date: str,
    days: int | None = 120,
) -> pd.DataFrame | None:
    """Fetch OHLCV history up to analysis_date from the SQLite cache."""
    try:
        _ensure_config_cache_dir()
        df = sqlite_cache.load_ohlcv(ticker, end_date=analysis_date)
        if df.empty or "Close" not in df.columns or "Date" not in df.columns:
            return None
        required = {"Open", "High", "Low", "Close"}
        if not required.issubset(df.columns):
            return None
        df = df.reset_index(drop=True)
        # Drop rows with NaN in any price column (matches Dashboard fix).
        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        if days is not None:
            df = df.tail(days).reset_index(drop=True)
        return df
    except Exception:
        traceback.print_exc()
        return None


def _fmt_num(value: float | None, decimals: int = 2) -> str:
    if value is None or math.isnan(value):
        return "—"
    return f"{value:,.{decimals}f}"


def _fmt_signed(value: float | None, decimals: int = 2, suffix: str = "") -> str:
    if value is None or math.isnan(value):
        return "—"
    return f"{value:+.{decimals}f}{suffix}"


def _pnl_class(value: float | None) -> str:
    if value is None or math.isnan(value) or value == 0:
        return "neutral"
    return "profit" if value > 0 else "loss"


def _build_metrics_html(
    ticker: str,
    holding: dict[str, Any] | None,
    df: pd.DataFrame | None,
    trades_by_date: dict[str, dict[str, dict[str, Any]]],
    analysis_date: str,
) -> str:
    """Build the five-metric header HTML used in the screenshot card."""
    symbol = _currency_symbol(ticker)
    name = holding["name"] if holding else ticker
    code = ticker

    latest_close: float | None = None
    prev_close: float | None = None
    if df is not None and not df.empty:
        latest_close = float(df.iloc[-1]["Close"])
        if len(df) >= 2:
            prev_close = float(df.iloc[-2]["Close"])

    quantity = holding["quantity"] if holding else 0.0
    cost_price = holding["cost_price"] if holding else 0.0

    market_value = quantity * latest_close if latest_close is not None else None
    total_cost = quantity * cost_price if cost_price else None
    position_pnl = (
        (market_value - total_cost) if market_value is not None and total_cost is not None else None
    )
    position_pnl_pct = (
        (position_pnl / total_cost * 100) if position_pnl is not None and total_cost else None
    )
    daily_pnl = (
        (latest_close - prev_close) * quantity
        if latest_close is not None and prev_close is not None and quantity
        else None
    )
    daily_pct = (
        (latest_close - prev_close) / prev_close * 100
        if latest_close is not None and prev_close and prev_close
        else None
    )

    day_trades = trades_by_date.get(analysis_date, {})
    buy = day_trades.get("buy")
    sell = day_trades.get("sell")
    if sell and sell["qty"]:
        trade_text = f"卖出 {sell['qty']:,.0f} 股"
    elif buy and buy["qty"]:
        trade_text = f"买入 {buy['qty']:,.0f} 股"
    else:
        trade_text = "—"

    blocks = [
        ("市值 / 数量", f"{symbol}{_fmt_num(market_value)}<br><span class='sub'>{_fmt_num(quantity, 0)} 股</span>"),
        (
            "现价 / 成本",
            f"{symbol}{_fmt_num(latest_close)}<br><span class='sub'>成本 {symbol}{_fmt_num(cost_price)}</span>",
        ),
        (
            "当日盈亏",
            f"<span class='{_pnl_class(daily_pnl)}'>{_fmt_signed(daily_pnl)}</span>"
            f"<br><span class='sub {_pnl_class(daily_pct)}'>{_fmt_signed(daily_pct, 2, '%')}</span>",
        ),
        (
            "持仓盈亏",
            f"<span class='{_pnl_class(position_pnl)}'>{_fmt_signed(position_pnl)}</span>"
            f"<br><span class='sub {_pnl_class(position_pnl_pct)}'>{_fmt_signed(position_pnl_pct, 2, '%')}</span>",
        ),
        ("当日交易", f"{trade_text}<br><span class='sub'>{analysis_date}</span>"),
    ]

    cells = ""
    for label, value in blocks:
        cells += f"""
        <div class="metric-block">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """

    return f"""
    <div class="stock-header">
        <div class="stock-info">
            <span class="stock-name">{name}</span>
            <span class="stock-code">{code}</span>
        </div>
        <span class="subtitle">技术分析</span>
    </div>
    <div class="metrics">{cells}</div>
    """


def _build_candlestick_svg(
    df: pd.DataFrame,
    width: int,
    height: int,
    cost_price: float | None = None,
    trades_by_date: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> str:
    """Build a dark-themed SVG candlestick chart with price axis and grid."""
    if df is None or df.empty:
        return ""

    n = len(df)
    padding_left = 24
    padding_right = 64  # room for price axis
    padding_top = 24
    padding_bottom = 34  # room for date labels
    chart_w = width - padding_left - padding_right
    chart_h = height - padding_top - padding_bottom

    has_volume = "Volume" in df.columns and df["Volume"].notna().any()
    volume_ratio = 0.18 if has_volume else 0.0
    volume_h = chart_h * volume_ratio
    price_h = chart_h - volume_h - 8  # gap between price and volume

    high = float(df["High"].max())
    low = float(df["Low"].min())
    latest_close = float(df.iloc[-1]["Close"])

    # Make sure the cost price is visible inside the y-range.
    if cost_price is not None and cost_price > 0:
        high = max(high, cost_price)
        low = min(low, cost_price)

    if high == low or math.isnan(high) or math.isnan(low):
        high = (high if not math.isnan(high) else 0) + 1
        low = (low if not math.isnan(low) else 0) - 1

    # Add a little headroom so markers/labels don't clip.
    range_pad = (high - low) * 0.05
    high += range_pad
    low -= range_pad

    def y(price: float) -> float:
        return padding_top + price_h * (high - price) / (high - low)

    candle_gap = chart_w / max(n, 1)
    candle_w = candle_gap * 0.55

    elements: list[str] = []

    # Horizontal grid lines + right price axis labels.
    grid_count = 5
    for i in range(grid_count + 1):
        ratio = i / grid_count
        price_level = low + (high - low) * (1 - ratio)
        gy = padding_top + price_h * ratio
        elements.append(
            f'<line x1="{padding_left}" y1="{gy:.1f}" x2="{width - padding_right}" '
            f'y2="{gy:.1f}" stroke="#1e293b" stroke-width="1"/>'
        )
        elements.append(
            f'<text x="{width - padding_right + 6}" y="{gy + 4:.1f}" '
            f'font-size="11" fill="#64748b" text-anchor="start">{price_level:,.2f}</text>'
        )

    # Highlight the latest close on the right axis.
    latest_y = y(latest_close)
    elements.append(
        f'<rect x="{width - padding_right + 2}" y="{latest_y - 9:.1f}" '
        f'width="{padding_right - 8}" height="18" rx="3" fill="#3b82f6"/>'
    )
    elements.append(
        f'<text x="{width - 6}" y="{latest_y + 4:.1f}" font-size="11" fill="#fff" '
        f'font-weight="700" text-anchor="end">{latest_close:,.2f}</text>'
    )

    # Axis lines (price area).
    elements.append(
        f'<line x1="{padding_left}" y1="{padding_top}" x2="{padding_left}" '
        f'y2="{padding_top + price_h}" stroke="#334155" stroke-width="1"/>'
    )
    elements.append(
        f'<line x1="{padding_left}" y1="{padding_top + price_h}" '
        f'x2="{width - padding_right}" y2="{padding_top + price_h}" '
        f'stroke="#334155" stroke-width="1"/>'
    )

    # Volume scale.
    vol_max = 0.0
    if has_volume:
        vol_max = float(df["Volume"].max())
        if vol_max <= 0:
            has_volume = False

    def vy(vol: float) -> float:
        if not has_volume or vol_max <= 0:
            return padding_top + price_h + 8 + volume_h
        return padding_top + price_h + 8 + volume_h * (1 - vol / vol_max)

    for i, (_, row) in enumerate(df.iterrows()):
        open_p = float(row["Open"])
        close_p = float(row["Close"])
        high_p = float(row["High"])
        low_p = float(row["Low"])
        date = str(row["Date"])[:10]
        volume = float(row["Volume"]) if has_volume and not pd.isna(row.get("Volume")) else 0.0

        cx = padding_left + candle_gap * i + candle_gap / 2
        is_up = close_p >= open_p
        color = "#ef4444" if is_up else "#10b981"  # Chinese convention: red=up, green=down

        # Volume bar.
        if has_volume and volume > 0:
            v_top = vy(volume)
            v_bar_w = max(candle_w * 0.8, 1)
            elements.append(
                f'<rect x="{cx - v_bar_w/2:.1f}" y="{v_top:.1f}" width="{v_bar_w:.1f}" '
                f'height="{padding_top + price_h + 8 + volume_h - v_top:.1f}" '
                f'fill="{color}" opacity="0.5"/>'
            )

        # Wick.
        elements.append(
            f'<line x1="{cx:.1f}" y1="{y(high_p):.1f}" x2="{cx:.1f}" y2="{y(low_p):.1f}" '
            f'stroke="{color}" stroke-width="1"/>'
        )
        # Body.
        top = min(y(open_p), y(close_p))
        body_h = max(abs(y(open_p) - y(close_p)), 1)
        elements.append(
            f'<rect x="{cx - candle_w/2:.1f}" y="{top:.1f}" width="{candle_w:.1f}" '
            f'height="{body_h:.1f}" fill="{color}" rx="1"/>'
        )

        # Date label every few candles.
        if n <= 8 or i % max(1, n // 6) == 0:
            elements.append(
                f'<text x="{cx:.1f}" y="{height - 8}" text-anchor="middle" '
                f'font-size="10" fill="#64748b">{date[-5:]}</text>'
            )

        # Trade markers (B/S) on the candle day.
        day_trades = (trades_by_date or {}).get(date, {})
        buy = day_trades.get("buy")
        sell = day_trades.get("sell")
        if sell and sell["qty"] > 0:
            y_pos = max(y(high_p) - 16, padding_top + 10)
            elements.append(
                f'<g transform="translate({cx:.1f},{y_pos:.1f})">'
                f'<circle r="10" fill="#10b981" stroke="#0f172a" stroke-width="2"/>'
                f'<text dy="0.35em" text-anchor="middle" font-size="11" fill="#fff" font-weight="700">S</text>'
                f'</g>'
            )
        if buy and buy["qty"] > 0:
            y_pos = min(y(low_p) + 16, padding_top + price_h - 10)
            elements.append(
                f'<g transform="translate({cx:.1f},{y_pos:.1f})">'
                f'<circle r="10" fill="#ef4444" stroke="#0f172a" stroke-width="2"/>'
                f'<text dy="0.35em" text-anchor="middle" font-size="11" fill="#fff" font-weight="700">B</text>'
                f'</g>'
            )

    # Cost price dashed line (always inside the padded range now).
    if cost_price is not None and cost_price > 0:
        cy = y(cost_price)
        elements.append(
            f'<line x1="{padding_left}" y1="{cy:.1f}" x2="{width - padding_right}" y2="{cy:.1f}" '
            f'stroke="#d97706" stroke-width="2" stroke-dasharray="6,4"/>'
        )
        label_x = width - padding_right - 6
        # Keep label inside chart area, slightly above the line.
        label_y = max(cy - 8, padding_top + 12)
        elements.append(
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="end" '
            f'font-size="11" fill="#d97706" font-weight="600">成本 {cost_price:,.3f}</text>'
        )

    return f'<svg viewBox="0 0 {width} {height}" class="candlestick-chart">{ "".join(elements) }</svg>'


# Inline CSS for the screenshot card. Kept inside the module so the feature is
# self-contained and does not depend on external static files.
_SCREENSHOT_CSS = """
* { box-sizing: border-box; }
body {
    margin: 0;
    background: #0f172a;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans SC", sans-serif;
    color: #e2e8f0;
}
.card {
    width: {width}px;
    padding: 24px;
    background: #1e293b;
    border-radius: 12px;
}
.card-title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    font-size: 14px;
    color: #94a3b8;
    font-weight: 600;
}
.stock-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 16px;
}
.stock-info { display: flex; align-items: baseline; gap: 12px; }
.stock-name { font-size: 26px; font-weight: 700; color: #f8fafc; }
.stock-code { font-size: 14px; color: #94a3b8; }
.subtitle { font-size: 13px; color: #64748b; }
.metrics {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin-bottom: 16px;
}
.metric-block {
    background: #0f172a;
    border-radius: 8px;
    padding: 12px 10px;
}
.metric-label {
    font-size: 11px;
    color: #64748b;
    margin-bottom: 6px;
}
.metric-value {
    font-size: 18px;
    font-weight: 700;
    color: #f1f5f9;
    line-height: 1.3;
}
.metric-value .sub {
    font-size: 11px;
    font-weight: 400;
    color: #94a3b8;
}
.profit { color: #ef4444; }
.loss { color: #10b981; }
.neutral { color: #94a3b8; }
.chart-wrap {
    background: #0f172a;
    border-radius: 8px;
    padding: 10px;
}
.candlestick-chart { display: block; width: 100%; height: auto; }
"""


def _build_screenshot_html(
    ticker: str,
    metrics_html: str,
    svg_chart: str,
    width: int,
    height: int,
) -> str:
    """Assemble the full HTML document for the screenshot."""
    css = _SCREENSHOT_CSS.replace("{width}", str(width))
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{ticker} snapshot</title>
    <style>{css}</style>
</head>
<body>
    <div class="card">
        <div class="card-title">个股速览与决策舱</div>
        {metrics_html}
        <div class="chart-wrap">
            {svg_chart}
        </div>
    </div>
</body>
</html>"""


def _html_to_png(html_path: Path, png_path: Path, width: int, height: int) -> Path:
    """Render a local HTML file to PNG using Playwright."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_viewport_size({"width": width, "height": height})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_load_state("domcontentloaded")
        # SVG rendering is synchronous; give fonts a moment to settle.
        page.wait_for_timeout(500)
        page.screenshot(path=str(png_path), type="png", full_page=True)
        browser.close()
    return png_path


def generate_stock_screenshot(
    ticker: str,
    analysis_date: str,
    output_path: str | Path,
    holding: dict[str, Any] | None = None,
    chart_days: int = 120,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> Path | None:
    """Generate a PNG screenshot of the per-stock snapshot card.

    Args:
        ticker: Ticker symbol, e.g. ``AAPL`` or ``600006.SS``.
        analysis_date: Analysis date in ``YYYY-MM-DD`` format.
        output_path: Destination PNG path.
        holding: Optional pre-loaded holding dict with ``name``, ``quantity``,
            and ``cost_price``.  When omitted the holding is read from the
            configured portfolio holdings file.
        chart_days: Number of trading days to show in the candlestick chart.
        width: Screenshot width in pixels.
        height: Screenshot height in pixels.

    Returns:
        The path to the generated PNG, or ``None`` if generation failed.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if holding is None:
            holding = _load_portfolio_holding(ticker)

        df = _get_price_history(ticker, analysis_date, days=chart_days)
        trades = _load_transactions_by_ticker(ticker)
        trades_by_date = _aggregate_trades(trades)

        metrics_html = _build_metrics_html(
            ticker, holding, df, trades_by_date, analysis_date
        )

        cost_price = holding["cost_price"] if holding else None
        svg_chart = _build_candlestick_svg(df, width, height - 200, cost_price, trades_by_date)

        html = _build_screenshot_html(ticker, metrics_html, svg_chart, width, height)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write(html)
            html_path = Path(f.name)

        try:
            _html_to_png(html_path, output_path, width, height)
        finally:
            with suppress(Exception):
                html_path.unlink()

        return output_path
    except Exception:
        traceback.print_exc()
        return None


def set_cache_dir(cache_dir: str | Path) -> None:
    """Convenience helper to point the screenshot module at a custom cache dir."""
    set_config({"data_cache_dir": str(cache_dir)})
