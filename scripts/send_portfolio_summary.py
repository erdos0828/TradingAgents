#!/usr/bin/env python3
"""Summarize latest analysis reports for portfolio holdings and render an HTML page.

Reads portfolio holdings, scans the latest reports/{ticker}/{date}_{time}/
directories, extracts ratings/theses, reads cached OHLCV prices, calculates
P&L, and writes a styled HTML file named by today's date.

Usage:
    .venv/bin/python scripts/send_portfolio_summary.py
    .venv/bin/python scripts/send_portfolio_summary.py --holdings data/portfolio_holdings.json
    .venv/bin/python scripts/send_portfolio_summary.py --days 5
    .venv/bin/python scripts/send_portfolio_summary.py --output-dir reports
"""

import argparse
import html
import json
import math
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from tradingagents.dataflows import sqlite_cache
from tradingagents.dataflows.config import set_config

# Load environment variables from .env (kept for other env-based config if needed)
load_dotenv()


def _load_holdings(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("holdings", [])


def _parse_date_time(dirname: str) -> datetime:
    """Parse directory name like '2026-08-19_121650' into datetime."""
    try:
        return datetime.strptime(dirname, "%Y-%m-%d_%H%M%S")
    except ValueError:
        return datetime.min


def _find_latest_report_dir(ticker: str, reports_dir: Path) -> Path | None:
    ticker_dir = reports_dir / ticker
    if not ticker_dir.exists():
        return None
    dirs = [d for d in ticker_dir.iterdir() if d.is_dir()]
    if not dirs:
        return None
    dirs.sort(key=lambda d: _parse_date_time(d.name), reverse=True)
    return dirs[0]


def _find_past_report_dirs(ticker: str, reports_dir: Path, days: int) -> list[Path]:
    """Find past N distinct-day report directories (excluding latest)."""
    ticker_dir = reports_dir / ticker
    if not ticker_dir.exists():
        return []
    dirs = [d for d in ticker_dir.iterdir() if d.is_dir()]
    dirs.sort(key=lambda d: _parse_date_time(d.name), reverse=True)

    seen_dates = set()
    result = []
    for d in dirs[1:]:
        date = d.name[:10]
        if date not in seen_dates:
            seen_dates.add(date)
            result.append(d)
        if len(result) >= days:
            break
    return result


def _recent_dates(target_date: str, days: int) -> list[str]:
    """Return the last `days` calendar dates ending at target_date, newest first."""
    base = datetime.strptime(target_date, "%Y-%m-%d")
    return [(base - __import__("datetime").timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]


def _get_recent_signals(ticker: str, reports_dir: Path, target_date: str, days: int = 7) -> list[dict]:
    """Return recent `days` calendar-day PM ratings for a ticker.

    Each entry is {"date": "YYYY-MM-DD", "rating": "Buy"|"Sell"|"Hold"|"N/A"|"X"}.
    Missing days are marked as "X".
    """
    ticker_dir = reports_dir / ticker
    date_to_rating: dict[str, str] = {}
    if ticker_dir.exists():
        for d in ticker_dir.iterdir():
            if not d.is_dir():
                continue
            date = d.name[:10]
            if date > target_date or not _recent_dates(target_date, days).__contains__(date):
                continue
            complete = d / "complete_report.md"
            if not complete.exists():
                continue
            try:
                text = complete.read_text(encoding="utf-8")
                pm = _extract_section(text, "V. Portfolio Manager Decision")
                rating = _extract_pm_rating(pm)
                date_to_rating[date] = rating
            except Exception:
                continue

    result = []
    for date in _recent_dates(target_date, days):
        result.append({"date": date, "rating": date_to_rating.get(date, "X")})
    return result


def _extract_section(text: str, header: str) -> str:
    """Extract content under a markdown header."""
    pattern = rf"## {re.escape(header)}\n(.*?)(?=\n## |\n# |\Z)"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return ""
    return match.group(1).strip()


def _extract_pm_field(text: str, field: str) -> str:
    """Extract **Field**: value from Portfolio Manager section."""
    pattern = rf"\*\*{re.escape(field)}\*\*:\s*(.*?)(?=\n\*\*|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return ""
    value = match.group(1).strip()
    value = re.sub(r"\*\*", "", value)
    return value


def _extract_pm_rating(text: str) -> str:
    """Extract **Rating**: XXX from Portfolio Manager section."""
    match = re.search(r"\*\*Rating\*\*:\s*\*{0,2}(\w+)\*{0,2}", text)
    if match:
        return match.group(1)
    return "N/A"


def _get_price_data(ticker: str, cache_dir: Path, target_date: str) -> tuple[float | None, float | None]:
    """Fetch latest and previous close price from cached OHLCV CSV for target_date."""
    df = _get_price_history(ticker, cache_dir, target_date, days=2)
    if df is None or df.empty:
        return None, None
    idx = df.index[-1]
    latest = float(df.loc[idx, "Close"])
    prev = float(df.loc[idx - 1, "Close"]) if idx > 0 else None
    return latest, prev


def _get_price_history(ticker: str, cache_dir: Path, target_date: str, days: int | None = 30) -> pd.DataFrame | None:
    """Fetch OHLCV history up to target_date from the SQLite cache.

    If ``days`` is None, returns all available history up to ``target_date``.
    """
    try:
        set_config({"data_cache_dir": str(cache_dir)})
        df = sqlite_cache.load_ohlcv(ticker, end_date=target_date)
        if df.empty or "Close" not in df.columns or "Date" not in df.columns:
            return None
        required = {"Open", "High", "Low", "Close"}
        if not required.issubset(df.columns):
            return None
        df = df.reset_index(drop=True)
        if days is not None:
            df = df.tail(days).reset_index(drop=True)
        return df
    except Exception:
        pass
    return None


def _load_transactions(transactions_path: Path) -> dict[str, list[dict]]:
    """Load normalized transaction records grouped by ticker."""
    if not transactions_path.exists():
        return {}
    try:
        with open(transactions_path, encoding="utf-8") as f:
            records = json.load(f)
    except Exception:
        return {}
    by_ticker: dict[str, list[dict]] = {}
    for r in records:
        ticker = r.get("ticker")
        if not ticker:
            continue
        by_ticker.setdefault(ticker, []).append(r)
    return by_ticker


def _aggregate_trades(trades: list[dict]) -> dict[str, dict[str, dict]]:
    """Aggregate trades by date and side. Returns {date: {side: {...}}}."""
    by_date: dict[str, dict[str, dict]] = {}
    for t in trades:
        date = t.get("date")
        side = t.get("side")
        if not date or side not in ("buy", "sell"):
            continue
        by_date.setdefault(date, {}).setdefault(side, {"qty": 0, "amount": 0.0, "trades": []})
        entry = by_date[date][side]
        entry["qty"] += t.get("quantity", 0)
        entry["amount"] += t.get("amount", 0.0)
        entry["trades"].append(t)
    return by_date


def _build_candlestick_svg(df: pd.DataFrame, width: int = 560, height: int = 180, trades: dict[str, dict] | None = None) -> str:
    """Build a lightweight SVG candlestick chart from OHLCV data."""
    if df is None or df.empty:
        return ""

    n = len(df)
    padding = 20
    chart_w = width - 2 * padding
    chart_h = height - 2 * padding

    high = df["High"].max()
    low = df["Low"].min()
    if high == low:
        high += 1
        low -= 1

    def y(price: float) -> float:
        return padding + chart_h * (high - price) / (high - low)

    candle_w = chart_w / max(n, 1) * 0.7
    gap = chart_w / max(n, 1)

    elements = []
    for i, (_, row) in enumerate(df.iterrows()):
        open_p = float(row["Open"])
        close_p = float(row["Close"])
        high_p = float(row["High"])
        low_p = float(row["Low"])
        date = str(row["Date"])[-5:]  # MM-DD

        cx = padding + gap * i + gap / 2
        is_up = close_p >= open_p
        color = "#d93025" if is_up else "#188038"  # Chinese convention: red=up, green=down

        # Wick
        elements.append(
            f'<line x1="{cx:.1f}" y1="{y(high_p):.1f}" x2="{cx:.1f}" y2="{y(low_p):.1f}" stroke="{color}" stroke-width="1" />'
        )
        # Body
        top = min(y(open_p), y(close_p))
        body_h = abs(y(open_p) - y(close_p))
        if body_h < 1:
            body_h = 1
        elements.append(
            f'<rect x="{cx - candle_w/2:.1f}" y="{top:.1f}" width="{candle_w:.1f}" height="{body_h:.1f}" fill="{color}" rx="1" />'
        )
        # Date label (every few candles)
        if n <= 10 or i % max(1, n // 5) == 0:
            elements.append(
                f'<text x="{cx:.1f}" y="{height - 4}" text-anchor="middle" font-size="9" fill="#747d8c">{date}</text>'
            )

    # Trade markers (B/S) overlaid on the candlestick chart
    if trades:
        for i, (_, candle) in enumerate(df.iterrows()):
            full_date = str(candle["Date"])
            day_trades = trades.get(full_date, {})
            if not day_trades:
                continue
            cx = padding + gap * i + gap / 2
            day_high = float(candle["High"])
            day_low = float(candle["Low"])

            # Sell markers above the high wick
            sell = day_trades.get("sell")
            if sell and sell["qty"] > 0:
                avg_price = sell["amount"] / sell["qty"] if sell["qty"] else 0.0
                y_pos = max(y(day_high) - 14, padding + 10)
                info = {
                    "date": full_date,
                    "side": "sell",
                    "totalQty": sell["qty"],
                    "avgPrice": avg_price,
                    "trades": [
                        {"side": t["side"], "qty": t["quantity"], "price": t["price"], "time": t.get("time", "")}
                        for t in sell["trades"]
                    ],
                }
                data_attr = html.escape(json.dumps(info, ensure_ascii=False))
                elements.append(
                    f'<g class="trade-marker" data-trade-info="{data_attr}" transform="translate({cx:.1f},{y_pos:.1f})">'
                    f'<circle r="8" fill="#188038" stroke="#fff" stroke-width="1.5"/>'
                    f'<text dy="0.35em" text-anchor="middle" font-size="9" fill="#fff" font-weight="700">S</text>'
                    f'</g>'
                )

            # Buy markers below the low wick
            buy = day_trades.get("buy")
            if buy and buy["qty"] > 0:
                avg_price = buy["amount"] / buy["qty"] if buy["qty"] else 0.0
                y_pos = min(y(day_low) + 14, height - padding - 10)
                info = {
                    "date": full_date,
                    "side": "buy",
                    "totalQty": buy["qty"],
                    "avgPrice": avg_price,
                    "trades": [
                        {"side": t["side"], "qty": t["quantity"], "price": t["price"], "time": t.get("time", "")}
                        for t in buy["trades"]
                    ],
                }
                data_attr = html.escape(json.dumps(info, ensure_ascii=False))
                elements.append(
                    f'<g class="trade-marker" data-trade-info="{data_attr}" transform="translate({cx:.1f},{y_pos:.1f})">'
                    f'<circle r="8" fill="#d93025" stroke="#fff" stroke-width="1.5"/>'
                    f'<text dy="0.35em" text-anchor="middle" font-size="9" fill="#fff" font-weight="700">B</text>'
                    f'</g>'
                )

    # Axis lines
    elements.insert(0, f'<line x1="{padding}" y1="{padding}" x2="{padding}" y2="{height - padding}" stroke="#dfe4ea" stroke-width="1" />')
    elements.insert(1, f'<line x1="{padding}" y1="{height - padding}" x2="{width - padding}" y2="{height - padding}" stroke="#dfe4ea" stroke-width="1" />')

    return f'<svg viewBox="0 0 {width} {height}" class="candlestick-chart">{ "".join(elements) }</svg>'


def _build_lightweight_chart(
    df: pd.DataFrame,
    ticker: str,
    trades: dict[str, dict] | None = None,
    height: int = 320,
    cost_price: float | None = None,
) -> str:
    """Build a TradingView lightweight-charts candlestick chart with B/S markers.

    Uses the built-in series.setMarkers() for B/S markers. Tooltips are shown
    via the crosshair move event when the cursor hovers a trading day.
    An optional dashed horizontal line marks the user's average cost price.
    """
    if df is None or df.empty:
        return ""

    candles = []
    for _, row in df.iterrows():
        candles.append({
            "time": str(row["Date"]),
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
        })

    markers = []
    trades_by_date: dict[str, list[dict]] = {}
    if trades:
        for date, day_trades in trades.items():
            day_entries = []
            for side in ("buy", "sell"):
                entry = day_trades.get(side)
                if entry and entry["qty"] > 0:
                    avg_price = round(entry["amount"] / entry["qty"], 4) if entry["qty"] else 0
                    markers.append({
                        "time": date,
                        "position": "belowBar" if side == "buy" else "aboveBar",
                        "color": "#e57373" if side == "buy" else "#6fc090",
                        "shape": "arrowUp" if side == "buy" else "arrowDown",
                        "text": "B" if side == "buy" else "S",
                        "size": 2,
                    })
                    day_entries.append({
                        "side": side,
                        "qty": entry["qty"],
                        "avgPrice": avg_price,
                    })
            if day_entries:
                trades_by_date[date] = day_entries

    markers.sort(key=lambda m: m["time"])

    has_cost = (
        cost_price is not None
        and isinstance(cost_price, (int, float))
        and not math.isnan(cost_price)
        and cost_price > 0
    )

    container_id = "chart-" + re.sub(r"[^a-zA-Z0-9]", "_", ticker)
    candles_json = json.dumps(candles, ensure_ascii=False)
    markers_json = json.dumps(markers, ensure_ascii=False)
    trades_by_date_json = json.dumps(trades_by_date, ensure_ascii=False)

    return (
        '<div id="' + container_id + '" class="lightweight-chart" style="height:' + str(height) + 'px;">'
        '<div class="chart-tooltip trade-tooltip">'
        '<div class="tooltip-title"></div>'
        '<div class="ohlc-row"><span>开</span><span class="ohlc-open"></span></div>'
        '<div class="ohlc-row"><span>高</span><span class="ohlc-high"></span></div>'
        '<div class="ohlc-row"><span>低</span><span class="ohlc-low"></span></div>'
        '<div class="ohlc-row"><span>收</span><span class="ohlc-close"></span></div>'
        '<div class="tooltip-body"></div>'
        '<div class="tooltip-summary"></div>'
        '</div>'
        '</div>\n'
        '<script>\n'
        '(function() {\n'
        '    var container = document.getElementById("' + container_id + '");\n'
        '    if (!container) return;\n'
        '    var chart = LightweightCharts.createChart(container, {\n'
        '        width: container.clientWidth,\n'
        '        height: ' + str(height) + ',\n'
        '        layout: { background: { color: "#ffffff" }, textColor: "#1f2328" },\n'
        '        grid: { vertLines: { color: "rgba(0, 0, 0, 0.05)" }, horzLines: { color: "rgba(0, 0, 0, 0.05)" } },\n'
        '        crosshair: { mode: LightweightCharts.CrosshairMode.Normal, vertLine: { color: "rgba(37, 99, 235, 0.2)" }, horzLine: { color: "rgba(37, 99, 235, 0.2)" } },\n'
        '        rightPriceScale: { borderColor: "rgba(0, 0, 0, 0.08)" },\n'
        '        timeScale: { borderColor: "rgba(0, 0, 0, 0.08)", timeVisible: false, barSpacing: 5, rightOffset: 12 },\n'
        '    });\n'
        '    var series = chart.addCandlestickSeries({\n'
        '        upColor: "#d93026", downColor: "#1e8e3e",\n'
        '        borderUpColor: "#d93026", borderDownColor: "#1e8e3e",\n'
        '        wickUpColor: "#d93026", wickDownColor: "#1e8e3e",\n'
        '    });\n'
        '    series.setData(' + candles_json + ');\n'
        '    series.setMarkers(' + markers_json + ');\n'
        + ('    series.createPriceLine({ price: ' + str(float(cost_price)) + ', color: "#d97706", lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: "成本" });\n' if has_cost else '')
        + '    function setDefaultRange() {\n'
        '        var data = ' + candles_json + ';\n'
        '        if (!data.length) return;\n'
        '        var last = data[data.length - 1].time;\n'
        '        var lastDate = new Date(last + "T00:00:00");\n'
        '        lastDate.setMonth(lastDate.getMonth() - 2);\n'
        '        var y = lastDate.getFullYear();\n'
        '        var m = lastDate.getMonth() + 1;\n'
        '        var d = lastDate.getDate();\n'
        '        var from = y + "-" + (m < 10 ? "0" + m : m) + "-" + (d < 10 ? "0" + d : d);\n'
        '        chart.timeScale().setVisibleRange({ from: from, to: last });\n'
        '    }\n'
        '    setDefaultRange();\n'
        '    window.addEventListener("resize", function() {\n'
        '        chart.resize(container.clientWidth, ' + str(height) + ');\n'
        '    });\n'
        '    var details = container.closest("details");\n'
        '    if (details) {\n'
        '        details.addEventListener("toggle", function() {\n'
        '            if (details.open) {\n'
        '                setTimeout(function() {\n'
        '                    chart.resize(container.clientWidth, ' + str(height) + ');\n'
        '                    setDefaultRange();\n'
        '                }, 0);\n'
        '            }\n'
        '        });\n'
        '    }\n'
        '\n'
        '    var tradesByDate = ' + trades_by_date_json + ';\n'
        '    var tooltip = container.querySelector(".chart-tooltip.trade-tooltip");\n'
        '    var titleEl = tooltip.querySelector(".tooltip-title");\n'
        '    var openEl = tooltip.querySelector(".ohlc-open");\n'
        '    var highEl = tooltip.querySelector(".ohlc-high");\n'
        '    var lowEl = tooltip.querySelector(".ohlc-low");\n'
        '    var closeEl = tooltip.querySelector(".ohlc-close");\n'
        '    var bodyEl = tooltip.querySelector(".tooltip-body");\n'
        '    var summaryEl = tooltip.querySelector(".tooltip-summary");\n'
        '\n'
        '    function fmtSide(side) {\n'
        '        return { cls: side === "buy" ? "side-buy" : "side-sell", text: side === "buy" ? "买入" : "卖出" };\n'
        '    }\n'
        '\n'
        '    chart.subscribeCrosshairMove(function(param) {\n'
        '        if (!param.time || !param.point) {\n'
        '            tooltip.style.display = "none";\n'
        '            return;\n'
        '        }\n'
        '        var data = param.seriesData.get(series);\n'
        '        if (!data) {\n'
        '            tooltip.style.display = "none";\n'
        '            return;\n'
        '        }\n'
        '        var timeStr = typeof param.time === "string" ? param.time : new Date(param.time * 1000).toISOString().slice(0, 10);\n'
        '        titleEl.textContent = timeStr.replace(/-/g, "/");\n'
        '        openEl.textContent = data.open.toFixed(2);\n'
        '        highEl.textContent = data.high.toFixed(2);\n'
        '        lowEl.textContent = data.low.toFixed(2);\n'
        '        closeEl.textContent = data.close.toFixed(2);\n'
        '\n'
        '        bodyEl.innerHTML = "";\n'
        '        var entries = tradesByDate[timeStr];\n'
        '        var totalQty = 0, totalAmount = 0;\n'
        '        if (entries) {\n'
        '            entries.forEach(function(e) {\n'
        '                var s = fmtSide(e.side);\n'
        '                var row = document.createElement("div");\n'
        '                row.className = "tooltip-row";\n'
        '                row.innerHTML = \'<span class="\' + s.cls + \'">\' + s.text + \'</span><span>\' + e.qty + \'@\' + (e.avgPrice ? e.avgPrice.toFixed(2) : \'-\') + \'</span>\';\n'
        '                bodyEl.appendChild(row);\n'
        '                totalQty += e.qty;\n'
        '                totalAmount += e.qty * e.avgPrice;\n'
        '            });\n'
        '        }\n'
        '        summaryEl.textContent = totalQty ? ("共 " + totalQty + " 股 · 均价 " + (totalAmount / totalQty).toFixed(2)) : "";\n'
        '        summaryEl.style.display = totalQty ? "block" : "none";\n'
        '\n'
        '        var tw = 200, th = 100, margin = 12;\n'
        '        var left = param.point.x + margin;\n'
        '        var top = param.point.y + margin;\n'
        '        if (left + tw > container.clientWidth) left = param.point.x - tw - margin;\n'
        '        if (top + th > container.clientHeight) top = param.point.y - th - margin;\n'
        '        tooltip.style.left = left + "px";\n'
        '        tooltip.style.top = top + "px";\n'
        '        tooltip.style.display = "block";\n'
        '    });\n'
        '\n'
        '})();\n'
        '</script>\n'
    )


def _fmt_number(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float) and math.isnan(value):
        return "N/A"
    return f"{value:,.{decimals}f}"


def _pnl_class(value: float | None) -> str:
    """Return CSS class for profit/loss following Chinese market convention (red=up/green=down)."""
    if value is None:
        return "neutral"
    if isinstance(value, float) and math.isnan(value):
        return "neutral"
    if value > 0:
        return "profit"
    if value < 0:
        return "loss"
    return "neutral"


def _rating_class(rating: str) -> str:
    text = rating.lower()
    if "buy" in text:
        return "rating-buy"
    if "overweight" in text:
        return "rating-overweight"
    if "sell" in text:
        return "rating-sell"
    if "underweight" in text:
        return "rating-underweight"
    if "hold" in text:
        return "rating-hold"
    return ""


def _market_region(ticker: str) -> str:
    """Classify a ticker into A-share or US stock based on its suffix."""
    if ticker.endswith(".SS") or ticker.endswith(".SZ"):
        return "A股"
    return "美股"


def _build_signal_activity_html(
    tickers: list[str],
    reports_dir: Path,
    target_date: str,
    days: int = 30,
    ticker_names: dict[str, str] | None = None,
) -> str:
    """Build a GitHub-style activity map of recent PM ratings.

    Each row is a ticker; columns are calendar days (newest -> oldest).
    A colored cell means a signal exists for that day; 'X' or unrecognized
    ratings are shown as empty (no signal).
    """
    if not tickers:
        return ""

    ticker_names = ticker_names or {}
    dates = _recent_dates(target_date, days)  # newest -> oldest
    weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
    date_labels = [d[8:] for d in dates]  # show day only

    rows_html: list[str] = []
    for ticker in tickers:
        display_name = html.escape(ticker_names.get(ticker, ticker))
        signals = _get_recent_signals(ticker, reports_dir, target_date, days)
        sig_by_date = {s["date"]: s["rating"] for s in signals}
        cells: list[str] = []
        for idx, d in enumerate(dates):
            dt = datetime.strptime(d, "%Y-%m-%d")
            prev_week = None
            if idx > 0:
                prev_dt = datetime.strptime(dates[idx - 1], "%Y-%m-%d")
                prev_week = prev_dt.isocalendar()[:2]
            week_start = idx > 0 and dt.isocalendar()[:2] != prev_week
            week_cls = " week-start" if week_start else ""
            rating = sig_by_date.get(d, "X")
            rating_cls = _rating_class(rating)
            tooltip = f"{display_name} · {d} 无信号"
            if rating == "X" or not rating_cls:
                cells.append(
                    f'<div class="activity-cell activity-empty{week_cls}" data-tooltip="{tooltip}"></div>'
                )
            else:
                tooltip = f"{display_name} · {d} {html.escape(rating)}"
                cells.append(
                    f'<div class="activity-cell {rating_cls}{week_cls}" data-tooltip="{tooltip}"></div>'
                )
        rows_html.append(
            '<div class="activity-row">'
            f'<div class="activity-ticker" title="{html.escape(ticker)}">{display_name}</div>'
            + "".join(cells)
            + "</div>"
        )

    header_cells: list[str] = []
    for idx, d in enumerate(dates):
        dt = datetime.strptime(d, "%Y-%m-%d")
        prev_week = None
        if idx > 0:
            prev_dt = datetime.strptime(dates[idx - 1], "%Y-%m-%d")
            prev_week = prev_dt.isocalendar()[:2]
        week_start = idx > 0 and dt.isocalendar()[:2] != prev_week
        week_cls = " week-start" if week_start else ""
        header_cells.append(
            f'<div class="activity-day-col{week_cls}">'
            f'<div class="activity-day-num">{html.escape(date_labels[idx])}</div>'
            f'<div class="activity-day-week">{html.escape(weekday_names[dt.weekday()])}</div>'
            '</div>'
        )

    legend_html = (
        '<div class="activity-legend">'
        '<span class="legend-item"><span class="legend-swatch activity-empty"></span>无信号</span>'
        '<span class="legend-item"><span class="legend-swatch rating-buy"></span>买入</span>'
        '<span class="legend-item"><span class="legend-swatch rating-overweight"></span>增持</span>'
        '<span class="legend-item"><span class="legend-swatch rating-sell"></span>卖出</span>'
        '<span class="legend-item"><span class="legend-swatch rating-underweight"></span>减持</span>'
        '<span class="legend-item"><span class="legend-swatch rating-hold"></span>持有</span>'
        '</div>'
    )

    return (
        '<div class="activity-map">'
        '<div class="panel-title">近30天信号</div>'
        '<div class="activity-header">'
        '<div class="activity-ticker"></div>'
        + "".join(header_cells)
        + "</div>"
        + "".join(rows_html)
        + legend_html
        + "</div>"
    )


def _build_region_summary_html(
    region_df: pd.DataFrame,
    reports_dir: Path,
    target_date: str,
    region_name: str,
    total_portfolio_cost: float = 0.0,
) -> str:
    """Build the executive dashboard summary for a market region."""
    total_market_value = float(region_df["市值"].sum()) if not region_df.empty else 0.0
    total_cost_value = float(region_df["持仓成本"].sum()) if not region_df.empty else 0.0
    total_pnl_raw = region_df["总收益"].sum()
    total_pnl = float(total_pnl_raw) if pd.notna(total_pnl_raw) else None
    total_return = (total_pnl / total_cost_value * 100) if total_pnl is not None and total_cost_value > 0 else None
    total_cls = _pnl_class(total_pnl)
    total_sign = "+" if total_pnl is not None and total_pnl > 0 else ""

    total_daily_pnl_raw = region_df["当日盈亏"].sum()
    total_daily_pnl = float(total_daily_pnl_raw) if pd.notna(total_daily_pnl_raw) else None
    daily_return = (
        (total_daily_pnl / total_cost_value * 100)
        if total_daily_pnl is not None and total_cost_value > 0
        else None
    )
    daily_cls = _pnl_class(total_daily_pnl)
    daily_sign = "+" if total_daily_pnl is not None and total_daily_pnl > 0 else ""

    region_weight = (
        (total_cost_value / total_portfolio_cost * 100)
        if total_portfolio_cost > 0
        else None
    )

    tickers = region_df["Ticker"].tolist()
    ticker_names = dict(zip(region_df["Ticker"], region_df["名称"], strict=False)) if "名称" in region_df.columns else {}
    activity_html = _build_signal_activity_html(tickers, reports_dir, target_date, ticker_names=ticker_names)

    return f"""
    <div class="region-dashboard">
        <div class="kpi-panel">
            <div class="panel-title">{html.escape(region_name)} 概览</div>
            <div class="kpi-grid">
                <div class="kpi">
                    <div class="kpi-label">证券市值</div>
                    <div class="kpi-value">{_fmt_number(total_market_value)}</div>
                </div>
                <div class="kpi">
                    <div class="kpi-label">持仓成本</div>
                    <div class="kpi-value">{_fmt_number(total_cost_value)}</div>
                </div>
                <div class="kpi {daily_cls}">
                    <div class="kpi-label">今日盈亏</div>
                    <div class="kpi-value">{daily_sign}{_fmt_number(total_daily_pnl)}</div>
                    <div class="kpi-change">{daily_sign}{_fmt_number(daily_return)}%</div>
                </div>
                <div class="kpi {total_cls}">
                    <div class="kpi-label">累计盈亏</div>
                    <div class="kpi-value">{total_sign}{_fmt_number(total_pnl)}</div>
                    <div class="kpi-change">{total_sign}{_fmt_number(total_return)}%</div>
                </div>
                <div class="kpi">
                    <div class="kpi-label">持仓数量</div>
                    <div class="kpi-value">{len(region_df)}</div>
                    <div class="kpi-change">只标的</div>
                </div>
                <div class="kpi">
                    <div class="kpi-label">组合权重</div>
                    <div class="kpi-value">{_fmt_number(region_weight, 1)}%</div>
                    <div class="kpi-change">占全仓成本</div>
                </div>
            </div>
        </div>
        <div class="signal-panel">
            {activity_html}
        </div>
    </div>
    """

def _build_cards_html(
    df: pd.DataFrame,
    cache_dir: Path,
    target_date: str,
    reports_dir: Path,
    report_server_url: str | None = None,
    transactions: dict[str, list[dict]] | None = None,
) -> str:
    """Build a holdings-list card layout grouped by market region with tabs."""

    def _card_html(row: pd.Series) -> str:
        ticker = html.escape(str(row["Ticker"]))
        name = html.escape(str(row.get("名称", ticker)))
        report_dir = html.escape(str(row["报告目录"]))
        rating = html.escape(str(row["最新评级"]))
        rating_cls = _rating_class(rating)
        summary = html.escape(str(row["Executive Summary"]))
        thesis = html.escape(str(row["Investment Thesis"])).replace("\n", "<br>")

        market_value = _fmt_number(row["市值"])
        qty = _fmt_number(row["股数"], 0)
        latest = _fmt_number(row["最新价"])
        cost = _fmt_number(row["成本价"])
        daily_pnl = _fmt_number(row["当日盈亏"])
        daily_ret = _fmt_number(row["当日盈亏率"])
        total_pnl = _fmt_number(row["总收益"])
        total_ret = _fmt_number(row["收益率"])

        daily_cls = _pnl_class(row["当日盈亏"])
        total_cls = _pnl_class(row["总收益"])

        sign_daily = "+" if row["当日盈亏"] is not None and row["当日盈亏"] > 0 else ""
        sign_total = "+" if row["总收益"] is not None and row["总收益"] > 0 else ""

        # Past ratings as compact tags for the header
        past_raw = str(row["过去评级"])
        past_tags = ""
        if past_raw:
            tags = []
            for line in past_raw.split("\n")[:3]:
                parts = line.split(": ")
                if len(parts) == 2:
                    d, r = parts
                    r_cls = _rating_class(r)
                    tags.append(f'<span class="past-tag {r_cls}">{html.escape(d)}: {html.escape(r)}</span>')
            past_tags = "".join(tags)

        # Candlestick chart with trade markers (show all available cache history)
        history = _get_price_history(ticker, cache_dir, target_date, days=None)
        ticker_trades = _aggregate_trades(transactions.get(ticker, [])) if transactions else {}
        candlestick_html = _build_lightweight_chart(history, ticker, ticker_trades, cost_price=row["成本价"]) if history is not None else ""

        report_link = ""
        if report_server_url:
            report_link = f'<a class="report-link" href="{html.escape(report_server_url)}#ticker={ticker}&date={report_dir}" target="_blank" rel="noopener">Report →</a>'

        return f"""
        <div class="holding-card">
            <div class="card-header">
                <div class="identity">
                    <div class="ticker-name">{name}</div>
                    <div class="ticker-code">{ticker}</div>
                </div>
                <div class="card-actions">
                    <span class="rating-tag {rating_cls}">{rating}</span>
                    {report_link}
                </div>
            </div>
            <div class="card-body">
                <div class="card-metrics">
                    <div class="metric">
                        <div class="metric-label">市值 / 数量</div>
                        <div class="metric-value">{market_value}</div>
                        <div class="metric-note">{qty} 股</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">现价 / 成本</div>
                        <div class="metric-value">{latest}</div>
                        <div class="metric-note">{cost}</div>
                    </div>
                    <div class="metric {daily_cls}">
                        <div class="metric-label">当日盈亏</div>
                        <div class="metric-value">{sign_daily}{daily_pnl}</div>
                        <div class="metric-note">{sign_daily}{daily_ret}%</div>
                    </div>
                    <div class="metric {total_cls}">
                        <div class="metric-label">持仓盈亏</div>
                        <div class="metric-value">{sign_total}{total_pnl}</div>
                        <div class="metric-note">{sign_total}{total_ret}%</div>
                    </div>
                </div>
                <div class="past-ratings">{past_tags}</div>
            </div>
            <details class="card-analysis">
                <summary>投资建议 &amp; 走势</summary>
                <div class="analysis-body">
                    <div class="analysis-section">
                        <div class="analysis-section-title">投资建议</div>
                        <p class="investment-summary">{summary}</p>
                        <p>{thesis}</p>
                    </div>
                    {f'<div class="analysis-section"><div class="analysis-section-title">历史走势</div>{candlestick_html}</div>' if candlestick_html else ''}
                </div>
            </details>
        </div>
        """

    # Group cards by market region
    groups: dict[str, list[str]] = {"A股": [], "美股": []}
    for _, row in df.iterrows():
        region = _market_region(str(row["Ticker"]))
        groups.setdefault(region, []).append(_card_html(row))

    total_portfolio_cost = float(df["持仓成本"].sum()) if not df.empty else 0.0

    # Preserve consistent tab order
    region_order = [r for r in ["A股", "美股"] if groups.get(r)]
    if not region_order:
        region_order = list(groups.keys())

    tab_buttons = []
    tab_panels = []
    for idx, region in enumerate(region_order):
        active_cls = " active" if idx == 0 else ""
        tab_id = f"tab-{region.replace('股', 'share')}"
        tab_buttons.append(
            f'<button class="market-tab{active_cls}" data-target="{tab_id}" onclick="switchMarketTab(\'{tab_id}\')">{region} ({len(groups[region])})</button>'
        )
        region_df = df[df["Ticker"].apply(_market_region) == region]
        summary_html = _build_region_summary_html(region_df, reports_dir, target_date, region, total_portfolio_cost)
        tab_panels.append(
            f'<div id="{tab_id}" class="market-panel{active_cls}">\n'
            + summary_html
            + '\n<div class="holdings-section">\n'
            + f'<div class="section-header"><h2 class="section-title">持仓明细</h2><span class="section-count">{len(groups[region])} 只标的</span></div>\n'
            + '<div class="holdings-grid">\n'
            + "\n".join(groups[region])
            + "\n</div>\n</div>\n</div>"
        )

    return (
        '<div class="market-tabs">\n'
        + "\n".join(tab_buttons)
        + '\n</div>\n'
        + "\n".join(tab_panels)
        + '\n<script>\n'
        + 'function switchMarketTab(targetId) {\n'
        + '    document.querySelectorAll(".market-panel").forEach(function(p) { p.classList.remove("active"); });\n'
        + '    document.querySelectorAll(".market-tab").forEach(function(t) { t.classList.remove("active"); });\n'
        + '    document.getElementById(targetId).classList.add("active");\n'
        + '    document.querySelector(\'.market-tab[data-target="\' + targetId + \'"]\').classList.add("active");\n'
        + '}\n'
        + '</script>\n'
    )


def _base_styles() -> str:
    return """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

        :root {
            --bg: #f6f7f9;
            --bg-elevated: #ffffff;
            --bg-card: #ffffff;
            --bg-hover: #f0f1f5;
            --border: rgba(0, 0, 0, 0.08);
            --border-strong: rgba(0, 0, 0, 0.16);
            --text: #1f2328;
            --text-secondary: #4a4f57;
            --text-muted: #8b949e;
            --accent: #2563eb;
            --accent-bright: #1d4ed8;
            --profit: #d93026;
            --loss: #1e8e3e;
            --neutral: #9aa0a6;
            --shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
            --radius: 12px;
            --radius-sm: 8px;
            --font-display: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-body: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-mono: 'JetBrains Mono', ui-monospace, monospace;
        }

        * { box-sizing: border-box; }

        html { scroll-behavior: smooth; }

        body {
            margin: 0;
            padding: 0;
            font-family: var(--font-body);
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 28px 32px 40px;
        }

        /* Header */
        .page-header {
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 24px;
            align-items: end;
            padding-bottom: 24px;
            margin-bottom: 28px;
            border-bottom: 1px solid var(--border);
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .brand-mark {
            width: 44px;
            height: 44px;
            border-radius: 12px;
            background: var(--accent);
            display: grid;
            place-items: center;
            color: #ffffff;
            font-family: var(--font-display);
            font-size: 22px;
            font-weight: 700;
            box-shadow: 0 6px 16px rgba(37, 99, 235, 0.22);
        }

        .brand-text h1 {
            margin: 0;
            font-family: var(--font-display);
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.02em;
            line-height: 1.15;
            color: var(--text);
        }

        .brand-text .subtitle {
            margin-top: 4px;
            font-family: var(--font-mono);
            font-size: 11px;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: var(--text-muted);
        }

        .controls {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 6px;
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            box-shadow: var(--shadow);
        }

        .controls label {
            font-family: var(--font-mono);
            font-size: 10px;
            font-weight: 600;
            color: var(--text-muted);
            letter-spacing: 0.06em;
            text-transform: uppercase;
            padding-left: 8px;
        }

        .controls select {
            padding: 9px 12px;
            border: 1px solid var(--border);
            border-radius: 8px;
            font-family: var(--font-mono);
            font-size: 13px;
            color: var(--text);
            background: var(--bg-card);
            min-width: 140px;
            cursor: pointer;
            outline: none;
            transition: all 0.2s ease;
        }

        .controls select:hover, .controls select:focus {
            border-color: var(--accent);
        }

        .controls button {
            padding: 9px 18px;
            border: 1px solid var(--accent);
            border-radius: 8px;
            background: var(--accent);
            color: #ffffff;
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .controls button:hover {
            background: var(--accent-bright);
            border-color: var(--accent-bright);
        }

        /* Market tabs */
        .market-tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 24px;
        }

        .market-tab {
            padding: 10px 22px;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            background: var(--bg-elevated);
            color: var(--text-secondary);
            font-family: var(--font-mono);
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.04em;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .market-tab:hover {
            border-color: var(--border-strong);
            color: var(--text);
            background: var(--bg-hover);
        }

        .market-tab.active {
            background: var(--accent);
            border-color: var(--accent);
            color: #ffffff;
        }

        .market-panel {
            display: none;
            animation: fadeUp 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        }

        .market-panel.active { display: block; }

        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(16px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Region dashboard */
        .region-dashboard {
            display: grid;
            grid-template-columns: 1fr 1.2fr;
            gap: 20px;
            margin-bottom: 32px;
        }

        .kpi-panel, .signal-panel {
            min-width: 0;
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 24px;
            box-shadow: var(--shadow);
        }

        .panel-title {
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 16px;
        }

        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 16px;
        }

        .kpi {
            display: flex;
            flex-direction: column;
            gap: 6px;
            padding: 12px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            min-width: 0;
        }

        .kpi-label {
            font-family: var(--font-mono);
            font-size: 10px;
            font-weight: 600;
            color: var(--text-muted);
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        .kpi-value {
            font-family: var(--font-mono);
            font-size: clamp(13px, 1.2vw, 18px);
            font-weight: 600;
            color: var(--text);
            letter-spacing: -0.02em;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .kpi-change {
            font-family: var(--font-mono);
            font-size: 12px;
            font-weight: 500;
            color: var(--text-muted);
        }

        .kpi.profit .kpi-value,
        .kpi.profit .kpi-change { color: var(--profit); }

        .kpi.loss .kpi-value,
        .kpi.loss .kpi-change { color: var(--loss); }

        .activity-map {
            overflow-x: auto;
            padding-bottom: 8px;
        }

        .activity-header, .activity-row {
            display: grid;
            grid-template-columns: 80px repeat(30, 16px);
            gap: 3px;
            align-items: center;
        }

        .activity-header {
            margin-bottom: 8px;
            align-items: end;
            min-height: 30px;
        }

        .activity-ticker {
            font-family: var(--font-body);
            font-size: 12px;
            font-weight: 500;
            color: var(--text-secondary);
            text-align: left;
            padding-right: 10px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .activity-day-col {
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-end;
            gap: 2px;
            line-height: 1;
            text-align: center;
            padding-bottom: 2px;
        }

        .activity-day-col.week-start::before,
        .activity-cell.week-start::before {
            content: "";
            position: absolute;
            left: -2px;
            top: 0;
            bottom: 0;
            width: 1px;
            background: var(--border-strong);
        }

        .activity-day-num {
            font-family: var(--font-mono);
            font-size: 8px;
            color: var(--text-secondary);
        }

        .activity-day-week {
            font-family: var(--font-mono);
            font-size: 8px;
            color: var(--text-muted);
        }

        .activity-cell {
            position: relative;
            width: 14px;
            height: 14px;
            border-radius: 3px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s ease;
            cursor: help;
        }

        .activity-cell:hover { transform: scale(1.15); z-index: 10; }

        .activity-cell::after {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%) translateY(-4px);
            padding: 5px 8px;
            background: rgba(31, 35, 40, 0.95);
            color: #f6f7f9;
            font-family: var(--font-mono);
            font-size: 10px;
            white-space: nowrap;
            border-radius: 5px;
            pointer-events: none;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.15s ease, visibility 0.15s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            z-index: 100;
        }

        .activity-cell:hover::after {
            opacity: 1;
            visibility: visible;
        }

        .activity-empty,
        .legend-swatch.activity-empty {
            background: #e8eaed;
            border: 1px solid rgba(0, 0, 0, 0.04);
        }

        .activity-cell.rating-buy,
        .legend-swatch.rating-buy {
            background: rgba(217, 48, 38, 0.9);
            border: 1px solid rgba(217, 48, 38, 0.25);
        }

        .activity-cell.rating-overweight,
        .legend-swatch.rating-overweight {
            background: rgba(239, 68, 68, 0.75);
            border: 1px solid rgba(239, 68, 68, 0.25);
        }

        .activity-cell.rating-sell,
        .legend-swatch.rating-sell {
            background: rgba(30, 142, 62, 0.9);
            border: 1px solid rgba(30, 142, 62, 0.25);
        }

        .activity-cell.rating-underweight,
        .legend-swatch.rating-underweight {
            background: rgba(74, 222, 128, 0.8);
            border: 1px solid rgba(74, 222, 128, 0.25);
        }

        .activity-cell.rating-hold,
        .legend-swatch.rating-hold {
            background: rgba(245, 158, 11, 0.9);
            border: 1px solid rgba(245, 158, 11, 0.25);
        }

        .activity-legend {
            display: flex;
            justify-content: flex-end;
            gap: 14px;
            margin-top: 14px;
            font-family: var(--font-body);
            font-size: 11px;
            color: var(--text-secondary);
            flex-wrap: wrap;
        }

        .legend-item {
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }

        .legend-swatch {
            width: 11px;
            height: 11px;
            border-radius: 2px;
        }

        /* Holdings section */
        .section-header {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            margin-bottom: 18px;
        }

        .section-title {
            font-family: var(--font-display);
            font-size: 22px;
            font-weight: 700;
            margin: 0;
            letter-spacing: -0.01em;
            color: var(--text);
        }

        .section-count {
            font-family: var(--font-mono);
            font-size: 12px;
            color: var(--text-muted);
            letter-spacing: 0.04em;
        }

        .holdings-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
        }

        .holding-card {
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            overflow: hidden;
            transition: all 0.25s ease;
            box-shadow: var(--shadow);
        }

        .holding-card:hover {
            border-color: var(--border-strong);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            transform: translateY(-2px);
        }

        .card-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 16px;
            padding: 20px 22px;
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
        }

        .identity {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .ticker-name {
            font-family: var(--font-display);
            font-size: 22px;
            font-weight: 600;
            color: var(--text);
            letter-spacing: -0.01em;
        }

        .ticker-code {
            font-family: var(--font-mono);
            font-size: 11px;
            color: var(--text-muted);
            letter-spacing: 0.05em;
        }

        .card-actions {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 8px;
        }

        .rating-tag {
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 6px;
            font-family: var(--font-mono);
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            background: var(--bg-hover);
            color: var(--text-secondary);
            border: 1px solid var(--border);
        }

        .rating-tag.rating-buy, .rating-tag.rating-overweight {
            background: rgba(217, 48, 38, 0.10);
            color: #b3261e;
            border-color: rgba(217, 48, 38, 0.2);
        }

        .rating-tag.rating-sell, .rating-tag.rating-underweight {
            background: rgba(30, 142, 62, 0.10);
            color: #137333;
            border-color: rgba(30, 142, 62, 0.2);
        }

        .rating-tag.rating-hold {
            background: rgba(245, 158, 11, 0.10);
            color: #b45309;
            border-color: rgba(245, 158, 11, 0.2);
        }

        .report-link {
            font-family: var(--font-mono);
            font-size: 10px;
            font-weight: 600;
            color: var(--accent);
            text-decoration: none;
            letter-spacing: 0.04em;
            transition: color 0.2s ease;
        }

        .report-link:hover { color: var(--accent-bright); }

        .card-body {
            padding: 18px 22px;
        }

        .card-metrics {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 14px;
            margin-bottom: 16px;
        }

        .metric {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .metric-label {
            font-family: var(--font-mono);
            font-size: 9px;
            font-weight: 600;
            color: var(--text-muted);
            letter-spacing: 0.07em;
            text-transform: uppercase;
        }

        .metric-value {
            font-family: var(--font-mono);
            font-size: 17px;
            font-weight: 600;
            color: var(--text);
            letter-spacing: -0.01em;
        }

        .metric-note {
            font-family: var(--font-mono);
            font-size: 11px;
            color: var(--text-muted);
        }

        .metric.profit .metric-value,
        .metric.profit .metric-note { color: var(--profit); }

        .metric.loss .metric-value,
        .metric.loss .metric-note { color: var(--loss); }

        .past-ratings {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            padding-top: 14px;
            border-top: 1px solid var(--border);
        }

        .past-tag {
            display: inline-flex;
            align-items: center;
            padding: 3px 8px;
            border-radius: 5px;
            font-family: var(--font-mono);
            font-size: 9px;
            font-weight: 600;
            letter-spacing: 0.04em;
            background: var(--bg-hover);
            color: var(--text-muted);
            border: 1px solid var(--border);
        }

        .past-tag.rating-buy, .past-tag.rating-overweight {
            background: rgba(217, 48, 38, 0.08);
            color: #b3261e;
            border-color: rgba(217, 48, 38, 0.15);
        }

        .past-tag.rating-sell, .past-tag.rating-underweight {
            background: rgba(30, 142, 62, 0.08);
            color: #137333;
            border-color: rgba(30, 142, 62, 0.15);
        }

        .past-tag.rating-hold {
            background: rgba(245, 158, 11, 0.08);
            color: #b45309;
            border-color: rgba(245, 158, 11, 0.12);
        }

        .card-analysis {
            border-top: 1px solid var(--border);
            background: var(--bg-card);
        }

        .card-analysis summary {
            cursor: pointer;
            padding: 14px 22px;
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.06em;
            color: var(--accent);
            list-style: none;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: color 0.2s ease;
        }

        .card-analysis summary::-webkit-details-marker { display: none; }

        .card-analysis summary::after {
            content: '+';
            font-size: 16px;
            font-weight: 400;
            transition: transform 0.2s ease;
        }

        .card-analysis[open] summary::after { transform: rotate(45deg); }

        .card-analysis summary:hover { color: var(--accent-bright); }

        .analysis-body {
            padding: 0 22px 22px;
        }

        .analysis-section {
            margin-bottom: 18px;
        }

        .analysis-section:last-child { margin-bottom: 0; }

        .analysis-section-title {
            font-family: var(--font-mono);
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.07em;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 10px;
        }

        .analysis-section p {
            margin: 0;
            line-height: 1.7;
            color: var(--text-secondary);
            font-size: 13px;
        }

        .investment-summary {
            color: var(--text);
            font-weight: 500;
            margin-bottom: 10px;
        }

        /* Chart */
        .lightweight-chart {
            position: relative;
            width: 100%;
            height: 320px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            overflow: hidden;
        }

        .trade-tooltip {
            display: none;
            position: absolute;
            background: rgba(31, 35, 40, 0.96);
            color: #f6f7f9;
            padding: 12px 16px;
            border-radius: var(--radius-sm);
            font-family: var(--font-mono);
            font-size: 11px;
            z-index: 1000;
            max-width: 260px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);
            pointer-events: none;
            line-height: 1.5;
        }

        .trade-tooltip .tooltip-title {
            font-family: var(--font-body);
            font-weight: 600;
            margin-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding-bottom: 6px;
            color: #93c5fd;
            font-size: 12px;
        }

        .trade-tooltip .tooltip-row {
            display: flex;
            justify-content: space-between;
            gap: 18px;
            margin: 2px 0;
        }

        .trade-tooltip .side-buy { color: #ff9aa2; }
        .trade-tooltip .side-sell { color: #a8e6cf; }

        .trade-tooltip .tooltip-summary {
            margin-top: 8px;
            padding-top: 6px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            font-weight: 600;
            color: #f6f7f9;
        }

        .trade-tooltip .ohlc-row {
            display: flex;
            justify-content: space-between;
            gap: 18px;
            margin: 2px 0;
            font-size: 10px;
        }

        .trade-tooltip .ohlc-row span:first-child { color: #9aa0a6; }

        .trade-tooltip .tooltip-body {
            margin-top: 8px;
            padding-top: 6px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }

        /* Footer & empty */
        footer {
            margin-top: 48px;
            padding-top: 24px;
            border-top: 1px solid var(--border);
            text-align: center;
            color: var(--text-muted);
            font-family: var(--font-mono);
            font-size: 10px;
            letter-spacing: 0.06em;
        }

        .empty-state {
            text-align: center;
            padding: 80px 24px;
            color: var(--text-muted);
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            font-family: var(--font-mono);
            font-size: 13px;
        }

        @media (max-width: 1100px) {
            .region-dashboard { grid-template-columns: 1fr; }
            .holdings-grid { grid-template-columns: 1fr; }
            .kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
            .kpi-value { font-size: 22px; }
        }

        @media (max-width: 720px) {
            .page-header { grid-template-columns: 1fr; }
            .controls { width: 100%; justify-content: space-between; }
            .kpi-grid { grid-template-columns: 1fr; }
            .card-metrics { grid-template-columns: 1fr; }
            .activity-header, .activity-row {
                grid-template-columns: 80px repeat(30, 12px);
                gap: 2px;
            }
            .activity-cell { width: 10px; height: 10px; }
            .activity-day-col.week-start::before,
            .activity-cell.week-start::before { left: -1px; }
            .activity-cell::after { font-size: 9px; padding: 4px 6px; }
            .activity-day-num { font-size: 6px; }
            .activity-day-week { font-size: 6px; }
            .container { padding: 20px 18px 32px; }
        }
    </style>
    """


def _build_html(
    df: pd.DataFrame,
    title: str,
    generated_at: str,
    cache_dir: Path,
    target_date: str,
    reports_dir: Path,
    report_server_url: str | None = None,
    transactions: dict[str, list[dict]] | None = None,
) -> str:
    cards_html = _build_cards_html(df, cache_dir, target_date, reports_dir, report_server_url, transactions)
    styles = _base_styles()
    safe_title = html.escape(title)
    safe_generated_at = html.escape(generated_at)
    return (
        '<!DOCTYPE html>\n'
        '<html lang="zh-CN">\n'
        '<head>\n'
        '    <meta charset="UTF-8">\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '    <title>' + safe_title + '</title>\n'
        '    <script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>\n'
        + styles +
        '</head>\n'
        '<body>\n'
        '    <div class="container">\n'
        '        <header class="page-header">\n'
        '            <div class="brand">\n'
        '                <div class="brand-mark">P</div>\n'
        '                <div class="brand-text">\n'
        '                    <h1>' + safe_title + '</h1>\n'
        '                    <div class="subtitle">生成于 ' + safe_generated_at + ' · 共 ' + str(len(df)) + ' 只持仓</div>\n'
        '                </div>\n'
        '            </div>\n'
        '        </header>\n'
        + cards_html +
        '        <footer>\n'
        '            数据来源：TradingAgents 分析报告 + cache OHLCV 收盘价\n'
        '        </footer>\n'
        '    </div>\n'
        '    <div id="trade-tooltip" class="trade-tooltip">\n'
        '        <div class="tooltip-title"></div>\n'
        '        <div class="tooltip-body"></div>\n'
        '        <div class="tooltip-summary"></div>\n'
        '    </div>\n'
        '    <script>\n'
        '        (function() {\n'
        '            const cards = document.querySelectorAll(\'.holding-card, .region-dashboard\');\n'
        '            cards.forEach((card, i) => {\n'
        '                card.style.opacity = \'0\';\n'
        '                card.style.transform = \'translateY(20px)\';\n'
        '                card.style.transition = \'opacity 0.5s cubic-bezier(0.22, 1, 0.36, 1), transform 0.5s cubic-bezier(0.22, 1, 0.36, 1)\';\n'
        '                setTimeout(() => {\n'
        '                    card.style.opacity = \'1\';\n'
        '                    card.style.transform = \'translateY(0)\';\n'
        '                }, 60 * i);\n'
        '            });\n'
        '        })();\n'
        '    </script>\n'
        '</body>\n'
        '</html>\n'
    )


def build_summary_data(
    holdings_path: Path,
    reports_dir: Path,
    cache_dir: Path,
    target_date: str | None = None,
    days: int = 3,
) -> tuple[pd.DataFrame, list[str]]:
    """Build the portfolio summary DataFrame for a given date (defaults to today)."""
    holdings = _load_holdings(holdings_path)
    if not holdings:
        return pd.DataFrame(), ["No holdings found."]

    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    rows: list[dict] = []
    errors: list[str] = []

    for h in holdings:
        ticker = h["ticker"]
        name = h.get("name", ticker)
        qty = float(h.get("quantity", 0))
        cost_price = float(h.get("cost_price", 0))

        # Find the latest report directory whose date <= target_date
        ticker_dir = reports_dir / ticker
        if not ticker_dir.exists():
            errors.append(f"No report found for {ticker}")
            continue

        dirs = [d for d in ticker_dir.iterdir() if d.is_dir()]
        dirs.sort(key=lambda d: _parse_date_time(d.name), reverse=True)

        eligible_dirs = [d for d in dirs if d.name[:10] <= target_date]
        if not eligible_dirs:
            errors.append(f"No report found for {ticker} on or before {target_date}")
            continue

        latest_dir = eligible_dirs[0]
        complete_report = latest_dir / "complete_report.md"
        if not complete_report.exists():
            errors.append(f"No complete_report.md for {ticker}")
            continue

        report_text = complete_report.read_text(encoding="utf-8")
        report_date = latest_dir.name[:10]
        report_dir_name = latest_dir.name

        pm_section = _extract_section(report_text, "V. Portfolio Manager Decision")
        raw_rating = _extract_pm_rating(pm_section)

        # Only treat as valid latest rating if the report is from the target date
        latest_rating = raw_rating if report_date == target_date else "N/A"

        investment_thesis = _extract_pm_field(pm_section, "Investment Thesis")
        executive_summary = _extract_pm_field(pm_section, "Executive Summary")

        # Past ratings (reverse chronological: newest first, line breaks inside cell)
        past_dirs = _find_past_report_dirs(ticker, reports_dir, days)
        past_ratings_lines = []
        for d in past_dirs:
            try:
                text = (d / "complete_report.md").read_text(encoding="utf-8")
                pm = _extract_section(text, "V. Portfolio Manager Decision")
                past_ratings_lines.append(f"{d.name[:10]}: {_extract_pm_rating(pm)}")
            except Exception:
                pass
        past_ratings_str = "\n".join(past_ratings_lines)

        latest_price, prev_price = _get_price_data(ticker, cache_dir, report_date)
        if latest_price is None:
            errors.append(f"Could not fetch price for {ticker}")
            continue

        market_value = latest_price * qty
        cost_value = cost_price * qty
        total_pnl = market_value - cost_value
        return_rate = (total_pnl / cost_value * 100) if cost_price > 0 else None

        daily_pnl = (latest_price - prev_price) * qty if prev_price is not None else None
        daily_return = ((latest_price - prev_price) / prev_price * 100) if prev_price not in (None, 0) else None

        rows.append({
            "Ticker": ticker,
            "名称": name,
            "最新评级": latest_rating,
            "Executive Summary": executive_summary,
            "Investment Thesis": investment_thesis,
            "过去评级": past_ratings_str,
            "成本价": cost_price,
            "最新价": latest_price,
            "股数": qty,
            "持仓成本": cost_value,
            "市值": market_value,
            "总收益": total_pnl,
            "收益率": return_rate,
            "当日盈亏": daily_pnl,
            "当日盈亏率": daily_return,
            "报告日期": report_date,
            "报告目录": report_dir_name,
        })

    if not rows:
        return pd.DataFrame(), errors

    df = pd.DataFrame(rows)
    column_order = [
        "Ticker", "名称", "最新评级", "Executive Summary", "Investment Thesis",
        "过去评级", "成本价", "最新价", "股数", "持仓成本", "市值",
        "当日盈亏", "当日盈亏率", "总收益", "收益率", "报告日期", "报告目录"
    ]
    return df[column_order], errors


def main():
    parser = argparse.ArgumentParser(description="Portfolio summary → HTML")
    parser.add_argument("--holdings", default="data/portfolio_holdings.json")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--cache-dir", default="cache")
    parser.add_argument("--days", type=int, default=3, help="How many past days' ratings to include")
    parser.add_argument("--output-dir", default=".", help="Directory to save the HTML file")
    parser.add_argument("--report-server-url", default="/reports", help="Base URL/path of the report browser for detail links")
    parser.add_argument("--transactions", default="data/transactions/transactions.json", help="Path to normalized transaction JSON")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    today_str = datetime.now().strftime("%Y-%m-%d")
    df, errors = build_summary_data(
        holdings_path=Path(args.holdings),
        reports_dir=Path(args.reports_dir),
        cache_dir=Path(args.cache_dir),
        target_date=today_str,
        days=args.days,
    )

    if df.empty:
        print("No data to write.")
        if errors:
            print("Errors:")
            for e in errors:
                print(f"  - {e}")
        return

    output_path = output_dir / f"portfolio_summary_{today_str}.html"

    title = f"持仓分析汇总 - {today_str}"
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    transactions = _load_transactions(Path(args.transactions))
    html_content = _build_html(df, title, generated_at, Path(args.cache_dir), today_str, Path(args.reports_dir), report_server_url=args.report_server_url, transactions=transactions)

    output_path.write_text(html_content, encoding="utf-8")

    print(f"Saved portfolio summary to: {output_path}")
    print(f"Rows: {len(df)}")
    if errors:
        print("Errors:")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
