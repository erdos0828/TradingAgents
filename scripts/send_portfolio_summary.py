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

# Load environment variables from .env (kept for other env-based config if needed)
load_dotenv()


def _load_holdings(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
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
    """Fetch OHLCV history up to target_date from cache.

    If ``days`` is None, returns all available history up to ``target_date``.
    Multiple cache files may exist; pick the one whose latest date is the
    most recent (but still <= target_date) to avoid stale partial files.
    """
    try:
        best_df: pd.DataFrame | None = None
        best_max_date: str | None = None
        for f in cache_dir.glob(f"{ticker}-YFin-data-*.csv"):
            df = pd.read_csv(f)
            if df.empty or "Close" not in df.columns or "Date" not in df.columns:
                continue
            required = {"Open", "High", "Low", "Close"}
            if not required.issubset(df.columns):
                continue
            df = df.sort_values("Date").reset_index(drop=True)
            df = df[df["Date"] <= target_date]
            if df.empty:
                continue
            max_date = str(df["Date"].iloc[-1])
            if best_max_date is None or max_date > best_max_date:
                best_max_date = max_date
                best_df = df if days is None else df.tail(days)
        if best_df is not None:
            return best_df.reset_index(drop=True)
    except Exception:
        pass
    return None


def _load_transactions(transactions_path: Path) -> dict[str, list[dict]]:
    """Load normalized transaction records grouped by ticker."""
    if not transactions_path.exists():
        return {}
    try:
        with open(transactions_path, "r", encoding="utf-8") as f:
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
    height: int = 360,
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
                        "color": "#d93025" if side == "buy" else "#188038",
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
        '        layout: { background: { color: "#ffffff" }, textColor: "#2f3542" },\n'
        '        grid: { vertLines: { color: "#f1f5f9" }, horzLines: { color: "#f1f5f9" } },\n'
        '        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },\n'
        '        rightPriceScale: { borderColor: "#dfe4ea" },\n'
        '        timeScale: { borderColor: "#dfe4ea", timeVisible: false, barSpacing: 4, rightOffset: 12 },\n'
        '    });\n'
        '    var series = chart.addCandlestickSeries({\n'
        '        upColor: "#d93025", downColor: "#188038",\n'
        '        borderUpColor: "#d93025", borderDownColor: "#188038",\n'
        '        wickUpColor: "#d93025", wickDownColor: "#188038",\n'
        '    });\n'
        '    series.setData(' + candles_json + ');\n'
        '    series.setMarkers(' + markers_json + ');\n'
        + ('    series.createPriceLine({ price: ' + str(float(cost_price)) + ', color: "#2563eb", lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: "成本" });\n' if has_cost else '')
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
    if "buy" in text or "overweight" in text:
        return "rating-buy"
    if "sell" in text or "underweight" in text:
        return "rating-sell"
    if "hold" in text:
        return "rating-hold"
    return ""


def _market_region(ticker: str) -> str:
    """Classify a ticker into A-share or US stock based on its suffix."""
    if ticker.endswith(".SS") or ticker.endswith(".SZ"):
        return "A股"
    return "美股"


def _build_cards_html(
    df: pd.DataFrame,
    cache_dir: Path,
    target_date: str,
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
            report_link = f'<a class="report-link" href="{html.escape(report_server_url)}#ticker={ticker}&date={report_dir}" target="_blank" rel="noopener">查看详细报告 →</a>'

        return f"""
        <div class="holding-card">
            <div class="card-header">
                <div class="ticker-block">
                    <div class="ticker-name-block">
                        <div class="ticker-name">{name}</div>
                        <div class="ticker-code">{ticker}</div>
                    </div>
                    <span class="rating-tag {rating_cls}">{rating}</span>
                </div>
                <div class="header-right">
                    <div class="past-ratings-header">{past_tags}</div>
                    {report_link}
                </div>
            </div>
            <div class="metrics-row">
                <div class="metric">
                    <div class="metric-label">市值 / 数量</div>
                    <div class="metric-main">{market_value}</div>
                    <div class="metric-sub">{qty} 股</div>
                </div>
                <div class="metric">
                    <div class="metric-label">现价 / 成本</div>
                    <div class="metric-main">{latest}</div>
                    <div class="metric-sub">{cost}</div>
                </div>
                <div class="metric {daily_cls}">
                    <div class="metric-label">当日盈亏</div>
                    <div class="metric-main">{sign_daily}{daily_pnl}</div>
                    <div class="metric-sub">{sign_daily}{daily_ret}%</div>
                </div>
                <div class="metric {total_cls}">
                    <div class="metric-label">持仓盈亏</div>
                    <div class="metric-main">{sign_total}{total_pnl}</div>
                    <div class="metric-sub">{sign_total}{total_ret}%</div>
                </div>
            </div>
            <div class="card-details">
                <details>
                    <summary>投资建议 &amp; 走势</summary>
                    <div class="detail-section">
                        <strong>投资建议</strong>
                        <p class="investment-summary">{summary}</p>
                        <p>{thesis}</p>
                    </div>
                    {f'<div class="detail-section"><strong>历史走势</strong>{candlestick_html}</div>' if candlestick_html else ''}
                </details>
            </div>
        </div>
        """

    # Group cards by market region
    groups: dict[str, list[str]] = {"A股": [], "美股": []}
    for _, row in df.iterrows():
        region = _market_region(str(row["Ticker"]))
        groups.setdefault(region, []).append(_card_html(row))

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
        tab_panels.append(
            f'<div id="{tab_id}" class="market-panel{active_cls}">\n'
            + '<div class="holdings-list">\n'
            + "\n".join(groups[region])
            + "\n</div>\n</div>"
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
        :root {
            --bg-color: #f5f7fa;
            --card-bg: #ffffff;
            --primary: #2c3e50;
            --accent: #3498db;
            --border: #dfe4ea;
            --text: #2f3542;
            --muted: #747d8c;
            --profit: #d93025;
            --loss: #188038;
            --neutral: #5f6368;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            padding: 24px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text);
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        header {
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 2px solid var(--border);
        }
        h1 { margin: 0 0 8px 0; font-size: 28px; color: var(--primary); }
        .meta { color: var(--muted); font-size: 14px; }
        .holdings-list {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .market-tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
            border-bottom: 2px solid var(--border);
            padding-bottom: 2px;
        }
        .market-tab {
            padding: 10px 20px;
            border: none;
            border-radius: 8px 8px 0 0;
            background: transparent;
            color: var(--muted);
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .market-tab:hover {
            background: #eef2f7;
            color: var(--primary);
        }
        .market-tab.active {
            background: var(--card-bg);
            color: var(--accent);
            box-shadow: 0 -2px 8px rgba(0,0,0,0.04);
            border-bottom: 2px solid var(--accent);
            margin-bottom: -2px;
        }
        .market-panel {
            display: none;
        }
        .market-panel.active {
            display: block;
        }
        .holding-card {
            background: var(--card-bg);
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            padding: 20px;
        }
        .card-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 16px;
        }
        .ticker-block {
            display: flex;
            align-items: center;
            gap: 12px;
            flex-shrink: 0;
        }
        .ticker-name-block {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        .ticker-name {
            font-size: 22px;
            font-weight: 700;
            color: var(--primary);
            line-height: 1.2;
        }
        .ticker-code {
            font-size: 13px;
            color: var(--muted);
            font-weight: 500;
        }
        .rating-tag {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            background: #e2e8f0;
            color: var(--primary);
        }
        .rating-tag.rating-buy, .rating-tag.rating-overweight { background: #ffebee; color: #c62828; }
        .rating-tag.rating-sell, .rating-tag.rating-underweight { background: #e8f5e9; color: #2e7d32; }
        .rating-tag.rating-hold { background: #fff8e1; color: #f9a825; }
        .header-right {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 8px;
            max-width: 65%;
        }
        .report-link {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 500;
            color: var(--accent);
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            text-decoration: none;
            transition: all 0.2s ease;
        }
        .report-link:hover {
            background: #dbeafe;
            border-color: #93c5fd;
            transform: translateY(-1px);
        }
        .past-ratings-header {
            display: flex;
            flex-wrap: wrap;
            justify-content: flex-end;
            gap: 6px;
        }
        .past-tag {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
            background: #f1f5f9;
            color: var(--muted);
            border: 1px solid var(--border);
            white-space: nowrap;
            transition: all 0.2s ease;
        }
        .past-tag.rating-buy, .past-tag.rating-overweight { background: #ffebee; color: #c62828; border-color: #ffcdd2; }
        .past-tag.rating-sell, .past-tag.rating-underweight { background: #e8f5e9; color: #2e7d32; border-color: #c8e6c9; }
        .past-tag.rating-hold { background: #fff8e1; color: #f9a825; border-color: #ffecb3; }
        .past-tag:hover { transform: translateY(-1px); box-shadow: 0 2px 4px rgba(0,0,0,0.08); }
        .summary-text {
            color: var(--muted);
            font-size: 13px;
            line-height: 1.5;
            text-align: right;
        }
        .metrics-row {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            padding: 16px 0;
            border-top: 1px solid var(--border);
            border-bottom: 1px solid var(--border);
        }
        .metric {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 4px;
        }
        .metric-label {
            font-size: 12px;
            color: var(--muted);
        }
        .metric-main {
            font-size: 22px;
            font-weight: 700;
            color: var(--text);
        }
        .metric-sub {
            font-size: 13px;
            color: var(--muted);
        }
        .metric.profit .metric-main,
        .metric.profit .metric-sub { color: var(--profit); }
        .metric.loss .metric-main,
        .metric.loss .metric-sub { color: var(--loss); }
        .card-details {
            margin-top: 16px;
        }
        .card-details details {
            font-size: 13px;
            color: var(--muted);
        }
        .card-details summary {
            cursor: pointer;
            font-weight: 600;
            color: var(--accent);
        }
        .detail-section {
            margin-top: 12px;
            padding: 12px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .detail-section p {
            margin: 6px 0 0 0;
            line-height: 1.6;
            color: var(--text);
        }
        .past-ratings { white-space: nowrap; }
        .investment-summary {
            font-weight: 600;
            color: var(--primary);
            margin-bottom: 12px;
            padding-bottom: 12px;
            border-bottom: 1px dashed var(--border);
        }
        .lightweight-chart {
            position: relative;
            width: 100%;
            height: 360px;
            margin-top: 10px;
            background: #ffffff;
            border-radius: 6px;
        }
        .trade-markers-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            pointer-events: none;
            overflow: hidden;
            z-index: 10;
        }
        .trade-marker-custom {
            position: absolute;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            font-weight: 700;
            color: #fff;
            pointer-events: auto;
            cursor: pointer;
            transition: transform 0.15s ease;
            z-index: 11;
        }
        .trade-marker-buy {
            background: #d93025;
            border: 1.5px solid #fff;
            box-shadow: 0 1px 3px rgba(217, 48, 37, 0.35);
        }
        .trade-marker-sell {
            background: #188038;
            border: 1.5px solid #fff;
            box-shadow: 0 1px 3px rgba(24, 128, 56, 0.35);
        }
        .trade-marker-custom:hover {
            transform: scale(1.25);
            z-index: 20;
        }
        .candlestick-chart {
            width: 100%;
            height: 180px;
            margin-top: 10px;
            background: #ffffff;
            border-radius: 6px;
        }
        .trade-marker { cursor: pointer; }
        .trade-marker:hover circle { stroke: var(--accent); stroke-width: 2.5; }
        .chart-tooltip {
            position: absolute;
            display: none;
        }
        .trade-tooltip {
            display: none;
            background: rgba(15, 23, 42, 0.95);
            color: #e2e8f0;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 13px;
            z-index: 1000;
            max-width: 280px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            pointer-events: none;
            line-height: 1.5;
        }
        .trade-tooltip .tooltip-title {
            font-weight: 600;
            margin-bottom: 8px;
            border-bottom: 1px solid #334155;
            padding-bottom: 6px;
            color: #fff;
        }
        .trade-tooltip .tooltip-row {
            display: flex;
            justify-content: space-between;
            gap: 16px;
            margin: 2px 0;
        }
        .trade-tooltip .side-buy { color: #ff6b6b; }
        .trade-tooltip .side-sell { color: #51cf66; }
        .trade-tooltip .tooltip-summary {
            margin-top: 8px;
            padding-top: 6px;
            border-top: 1px solid #334155;
            font-weight: 600;
            color: #fff;
        }
        .trade-tooltip .ohlc-row {
            display: flex;
            justify-content: space-between;
            gap: 16px;
            margin: 2px 0;
            font-size: 12px;
        }
        .trade-tooltip .ohlc-row span:first-child { color: #94a3b8; }
        .trade-tooltip .tooltip-body {
            margin-top: 8px;
            padding-top: 6px;
            border-top: 1px solid #334155;
        }
        footer {
            margin-top: 24px;
            text-align: center;
            color: var(--muted);
            font-size: 13px;
        }
        @media (max-width: 900px) {
            .metrics-row { grid-template-columns: repeat(2, 1fr); }
            .summary-text { display: none; }
            .past-ratings-header { display: none; }
            .header-right { max-width: 35%; }
        }
        @media (max-width: 480px) {
            .metrics-row { grid-template-columns: 1fr; }
            .card-header { flex-direction: column; }
            .header-right { align-items: flex-start; max-width: 100%; }
            .summary-text { text-align: left; }
        }
    </style>
    """


def _build_html(
    df: pd.DataFrame,
    title: str,
    generated_at: str,
    cache_dir: Path,
    target_date: str,
    report_server_url: str | None = None,
    transactions: dict[str, list[dict]] | None = None,
) -> str:
    cards_html = _build_cards_html(df, cache_dir, target_date, report_server_url, transactions)
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
        '        <header>\n'
        '            <h1>' + safe_title + '</h1>\n'
        '            <div class="meta">生成时间：' + safe_generated_at + ' &nbsp;|&nbsp; 共 ' + str(len(df)) + ' 只持仓</div>\n'
        '        </header>\n'
        + cards_html +
        '        <footer>\n'
        '            数据来源：TradingAgents 分析报告 + cache OHLCV 收盘价\n'
        '        </footer>\n'
        '    </div>\n'
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
        "过去评级", "成本价", "最新价", "股数", "市值",
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
    html_content = _build_html(df, title, generated_at, Path(args.cache_dir), today_str, report_server_url=args.report_server_url, transactions=transactions)

    output_path.write_text(html_content, encoding="utf-8")

    print(f"Saved portfolio summary to: {output_path}")
    print(f"Rows: {len(df)}")
    if errors:
        print("Errors:")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
