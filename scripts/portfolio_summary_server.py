#!/usr/bin/env python3
"""Dynamic portfolio summary web server.

Serves an HTML page that lets the user pick a date and generates the portfolio
summary on demand by scanning reports/{ticker}/{date}_{time}/ directories.

Usage:
    .venv/bin/python -m scripts.portfolio_summary_server
    .venv/bin/python -m scripts.portfolio_summary_server --port 8080
"""

import argparse
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template_string, request, send_from_directory

# Make sibling modules importable when running as `python -m scripts.xxx`
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from report_server import INDEX_HTML, list_report_files, scan_reports
from send_portfolio_summary import (
    _base_styles,
    _build_cards_html,
    _get_price_history,
    _get_recent_signals,
    _get_signal_outcomes,
    _aggregate_trades,
    _load_holdings,
    _load_transactions,
    _recent_dates,
    build_summary_data,
)
from tradingagents.dataflows import tradingview_ta_cache

load_dotenv()

app = Flask(__name__)

BASE_DIR = Path(os.getenv("TRADINGAGENTS_HOME", os.getcwd()))
HOLDINGS_PATH = Path(os.getenv("PORTFOLIO_HOLDINGS", BASE_DIR / "data" / "portfolio_holdings.json"))
REPORTS_DIR = Path(os.getenv("PORTFOLIO_REPORTS_DIR", BASE_DIR / "reports"))
CACHE_DIR = Path(os.getenv("PORTFOLIO_CACHE_DIR", BASE_DIR / "cache"))
DAYS = int(os.getenv("PORTFOLIO_PAST_DAYS", "3"))
REPORT_SERVER_URL = os.getenv("PORTFOLIO_REPORT_SERVER_URL", "/reports")
TRANSACTIONS_PATH = Path(os.getenv("PORTFOLIO_TRANSACTIONS", BASE_DIR / "data" / "transactions" / "transactions.json"))


def _available_dates() -> list[str]:
    """Return sorted unique report dates found under reports_dir."""
    dates = set()
    if not REPORTS_DIR.exists():
        return []
    for ticker_dir in REPORTS_DIR.iterdir():
        if not ticker_dir.is_dir():
            continue
        for run_dir in ticker_dir.iterdir():
            if run_dir.is_dir() and len(run_dir.name) >= 10:
                dates.add(run_dir.name[:10])
    return sorted(dates, reverse=True)


def _latest_available_date() -> str | None:
    dates = _available_dates()
    return dates[0] if dates else None


_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>持仓分析汇总</title>
    <script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
    {{ styles | safe }}
</head>
<body>
    <div class="container">
        <header class="page-header">
            <div class="brand">
                <div class="brand-mark">P</div>
                <div class="brand-text">
                    <h1>持仓分析汇总</h1>
                    <div class="subtitle">Portfolio Summary · 动态生成</div>
                </div>
            </div>
            <form class="controls" method="get" action="/">
                <label for="date">日期</label>
                <select name="date" id="date">
                    {% for d in available_dates %}
                    <option value="{{ d }}" {% if d == selected_date %}selected{% endif %}>{{ d }}</option>
                    {% endfor %}
                </select>
                <button type="submit">生成报告</button>
            </form>
        </header>
        {% if cards_html %}
        {{ cards_html | safe }}
        {% else %}
        <div class="empty-state">
            <p>暂无数据</p>
            {% if errors %}
            <ul style="text-align:left; display:inline-block;">
                {% for e in errors %}
                <li>{{ e }}</li>
                {% endfor %}
            </ul>
            {% endif %}
        </div>
        {% endif %}
        <footer>
            数据来源：TradingAgents 分析报告 + cache OHLCV 收盘价
        </footer>
    </div>
    <div id="trade-tooltip" class="trade-tooltip">
        <div class="tooltip-title"></div>
        <div class="tooltip-body"></div>
        <div class="tooltip-summary"></div>
    </div>
    <div id="activity-tooltip" class="activity-global-tooltip"></div>
    <script>
        (function() {
            const cards = document.querySelectorAll('.holding-card, .region-dashboard');
            cards.forEach((card, i) => {
                card.style.opacity = '0';
                card.style.transform = 'translateY(20px)';
                card.style.transition = 'opacity 0.5s cubic-bezier(0.22, 1, 0.36, 1), transform 0.5s cubic-bezier(0.22, 1, 0.36, 1)';
                setTimeout(() => {
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                }, 60 * i);
            });
            document.addEventListener('DOMContentLoaded', function() {
                const activityTooltip = document.getElementById('activity-tooltip');
                if (!activityTooltip) return;
                function positionTooltip(e) {
                    const margin = 12;
                    let left = e.clientX + margin;
                    let top = e.clientY + margin;
                    const rect = activityTooltip.getBoundingClientRect();
                    if (left + rect.width > window.innerWidth) {
                        left = e.clientX - rect.width - margin;
                    }
                    if (top + rect.height > window.innerHeight) {
                        top = e.clientY - rect.height - margin;
                    }
                    activityTooltip.style.left = left + 'px';
                    activityTooltip.style.top = top + 'px';
                }
                document.body.addEventListener('mouseover', function(e) {
                    const cell = e.target.closest('.activity-cell');
                    if (!cell) return;
                    activityTooltip.textContent = cell.getAttribute('data-tooltip');
                    activityTooltip.classList.add('visible');
                    positionTooltip(e);
                });
                document.body.addEventListener('mousemove', function(e) {
                    const cell = e.target.closest('.activity-cell');
                    if (!cell) return;
                    positionTooltip(e);
                });
                document.body.addEventListener('mouseout', function(e) {
                    const cell = e.target.closest('.activity-cell');
                    if (!cell) return;
                    activityTooltip.classList.remove('visible');
                });
            });
        })();
    </script>
</body>
</html>
"""


@app.route("/reports")
def report_index():
    """Serve the detailed report browser (merged from report_server.py)."""
    return Response(INDEX_HTML, mimetype="text/html; charset=utf-8")


@app.route("/dashboard")
def dashboard():
    """Serve the new TradingAgents dashboard (experimental UI redesign)."""
    dashboard_path = BASE_DIR / "cli" / "static" / "dashboard.html"
    if dashboard_path.exists():
        return Response(dashboard_path.read_text(encoding="utf-8"), mimetype="text/html; charset=utf-8")
    return "Dashboard not found", 404

@app.route("/dashboard2")
def dashboard2():
    """Serve the new TradingAgents dashboard (experimental UI redesign)."""
    dashboard_path = BASE_DIR / "cli" / "static" / "index.html"
    if dashboard_path.exists():
        return Response(dashboard_path.read_text(encoding="utf-8"), mimetype="text/html; charset=utf-8")
    return "Dashboard not found", 404


@app.route("/components/<path:file_path>")
def serve_component(file_path):
    """Serve static assets (JSX components / CSS) for the SPA dashboards."""
    components_dir = BASE_DIR / "cli" / "static" / "components"
    target = components_dir / file_path
    if not target.exists() or not target.is_file():
        return "Not found", 404
    real_path = target.resolve()
    if not str(real_path).startswith(str(components_dir.resolve())):
        return "Not found", 404
    mimetype = "text/css" if target.suffix == ".css" else "text/javascript"
    return Response(target.read_text(encoding="utf-8"), mimetype=f"{mimetype}; charset=utf-8")


# ---------------------------------------------------------------------------
# TradingView charting library assets + UDF datafeed endpoints.
#
# The stock overview panel is powered by the full TradingView charting
# library (the same engine behind the chanlun-pro charts). Candles are
# served from our own SQLite OHLCV cache through the UDF protocol below;
# daily bars are aggregated with pandas for the weekly / monthly views.
# ---------------------------------------------------------------------------

_TV_LIB_DIR = BASE_DIR / "cli" / "static" / "tv"
_TV_RESOLUTIONS = ["D", "W", "M"]


@app.route("/tv_lib/<path:file_path>")
def serve_tv_lib(file_path):
    """Serve the TradingView charting library and UDF datafeed bundle."""
    if not _TV_LIB_DIR.exists():
        return "TradingView library not installed", 404
    return send_from_directory(_TV_LIB_DIR, file_path)


def _tv_symbol_ticker(symbol: str) -> str:
    """Extract the ticker from a UDF symbol string ("SH:600006" / "600006.SS")."""
    return symbol.split(":")[-1]


def _tv_exchange(ticker: str) -> str:
    """Non-empty exchange is required by the library's SymbolInfo validation."""
    if ticker.endswith(".SS"):
        return "SSE"
    if ticker.endswith(".SZ"):
        return "SZSE"
    return "US"


def _tv_resample_daily(df: pd.DataFrame, resolution: str) -> pd.DataFrame:
    """Aggregate daily bars into weekly (W-FRI) or monthly (ME) bars."""
    rule = {"W": "W-FRI", "M": "ME"}.get(resolution)
    if rule is None:
        return df
    agg = (
        df.set_index("Date")
        .resample(rule)
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        .dropna(subset=["Open"])
        .reset_index()
    )
    return agg


@app.route("/tv/config")
def tv_config():
    return jsonify(
        {
            "supported_resolutions": _TV_RESOLUTIONS,
            "supports_group_request": False,
            "supports_marks": True,
            "supports_search": True,
            "supports_timescale_marks": False,
        }
    )


@app.route("/tv/search")
def tv_search():
    """Symbol search over the holdings list (kept minimal: no full exchange)."""
    query = request.args.get("query", "").lower()
    results = []
    for h in _load_holdings(HOLDINGS_PATH):
        ticker = h.get("ticker", "")
        name = h.get("name", "")
        if not ticker:
            continue
        if query in ticker.lower() or query in name.lower():
            results.append(
                {
                    "symbol": ticker,
                    "full_name": name,
                    "description": name,
                    "exchange": "",
                    "ticker": ticker,
                    "type": "stock",
                }
            )
    return jsonify(results)


@app.route("/tv/time")
def tv_time():
    return str(int(datetime.now().timestamp()))


@app.route("/tv/symbols")
def tv_symbols():
    ticker = _tv_symbol_ticker(request.args.get("symbol", ""))
    name = ticker
    for h in _load_holdings(HOLDINGS_PATH):
        if h.get("ticker") == ticker:
            name = h.get("name", ticker)
            break
    return jsonify(
        {
            "name": f"{name} ({ticker})",
            "ticker": ticker,
            "description": name,
            "type": "stock",
            "session": "24x7",
            "timezone": "Etc/UTC",
            "exchange": _tv_exchange(ticker),
            "listed_exchange": _tv_exchange(ticker),
            "format": "price",
            "pricescale": 100,
            "minmovement": 1,
            "has_intraday": False,
            "has_daily": True,
            "has_weekly_and_monthly": True,
            "supported_resolutions": _TV_RESOLUTIONS,
            "volume_precision": 0,
            "data_status": "endofday",
        }
    )


@app.route("/tv/history")
def tv_history():
    ticker = _tv_symbol_ticker(request.args.get("symbol", ""))
    resolution = request.args.get("resolution", "D")
    try:
        _from = int(request.args.get("from", "0"))
        _to = int(request.args.get("to", "9999999999"))
    except ValueError:
        return jsonify({"s": "error", "errmsg": "invalid from/to"})

    df = _get_price_history(ticker, CACHE_DIR, datetime.now().strftime("%Y-%m-%d"), days=None)
    if df is None or df.empty:
        return jsonify({"s": "no_data", "nextTime": None})
    if resolution in ("W", "M"):
        df = _tv_resample_daily(df, resolution)

    t_list, o_list, h_list, l_list, c_list, v_list = [], [], [], [], [], []
    bars = []
    for _, row in df.iterrows():
        try:
            ts = int(pd.Timestamp(row["Date"]).tz_localize("UTC").timestamp())
        except Exception:
            continue
        try:
            o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
        except (TypeError, ValueError):
            continue
        if math.isnan(o) or math.isnan(h) or math.isnan(l) or math.isnan(c):
            continue
        v = row.get("Volume")
        v = float(v) if v == v and not math.isnan(float(v)) else 0.0
        bars.append((ts, round(o, 4), round(h, 4), round(l, 4), round(c, 4), int(v)))

    # UDF semantics: when the library sends `countback` it asks for that many
    # bars counting back from `to` (the `from` bound is only a hint). Ignoring
    # it made every page return fewer bars than requested, so the library's
    # history paging shrank its window and stopped near the first page's
    # left edge instead of walking back through the full history.
    countback = request.args.get("countback")
    if countback:
        try:
            n = int(countback)
        except ValueError:
            n = 0
        bars = [b for b in bars if b[0] <= _to][-n:] if n > 0 else []
    else:
        bars = [b for b in bars if _from <= b[0] <= _to]

    if not bars:
        return jsonify({"s": "no_data", "nextTime": None})
    for ts, o, h, l, c, v in bars:
        t_list.append(ts)
        o_list.append(o)
        h_list.append(h)
        l_list.append(l)
        c_list.append(c)
        v_list.append(v)
    return jsonify({"s": "ok", "t": t_list, "o": o_list, "h": h_list, "l": l_list, "c": c_list, "v": v_list})


@app.route("/tv/marks")
def tv_marks():
    ticker = _tv_symbol_ticker(request.args.get("symbol", ""))
    try:
        _from = int(request.args.get("from", "0"))
        _to = int(request.args.get("to", "9999999999"))
    except ValueError:
        _from, _to = 0, 9999999999

    marks = []
    transactions = _load_transactions(TRANSACTIONS_PATH)
    aggregated = _aggregate_trades(transactions.get(ticker, [])) if transactions else {}
    idx = 0
    for date, day_trades in aggregated.items():
        try:
            ts = int(datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue
        if not (_from <= ts <= _to):
            continue
        for side in ("buy", "sell"):
            entry = day_trades.get(side)
            if not entry or entry["qty"] <= 0:
                continue
            avg_price = round(entry["amount"] / entry["qty"], 4) if entry["qty"] else 0
            marks.append(
                {
                    "id": f"trade-{idx}",
                    "time": ts,
                    # The library only honours named colors ("red"/"green",
                    # as stored by chanlun-pro) — rgba/hex fall back to the
                    # default orange.
                    "color": "red" if side == "buy" else "green",
                    "label": "B" if side == "buy" else "S",
                    "labelFontColor": "white",
                    "minSize": 24,
                    "text": f"{'买入' if side == 'buy' else '卖出'} {entry['qty']} @ {avg_price}",

                }
            )
            idx += 1
    return jsonify(marks)


def _dashboard_market(ticker: str) -> str:
    """Classify a ticker into a dashboard market key ('a-share' / 'us')."""
    if ticker.endswith(".SS") or ticker.endswith(".SZ"):
        return "a-share"
    return "us"


def _fmt_currency_signed(value: float, symbol: str) -> str:
    """Format a signed currency amount like '+¥8,320.45' / '-$1,245.60'."""
    sign = "+" if value >= 0 else "-"
    return f"{sign}{symbol}{abs(value):,.2f}"


def _build_dashboard_portfolio() -> dict:
    """Build the dashboard portfolio overview from real holdings and cached prices.

    Groups holdings by market, values them with the latest cached OHLCV close
    (previous close for daily change), and returns mock-compatible structures.
    """
    holdings = _load_holdings(HOLDINGS_PATH)
    target_date = datetime.now().strftime("%Y-%m-%d")

    raw: dict[str, list[dict]] = {"a-share": [], "us": []}
    errors: list[str] = []

    for h in holdings:
        ticker = h["ticker"]
        qty = float(h.get("quantity", 0))
        cost_price = float(h.get("cost_price", 0) or 0)

        df = _get_price_history(ticker, CACHE_DIR, target_date, days=2)
        if df is None or df.empty:
            errors.append(f"No cached price for {ticker}")
            continue

        latest = float(df.iloc[-1]["Close"])
        if math.isnan(latest):
            errors.append(f"Invalid cached price for {ticker}")
            continue
        prev = float(df.iloc[-2]["Close"]) if len(df) > 1 else None
        if prev is not None and math.isnan(prev):
            prev = None
        try:
            price_date = df.iloc[-1]["Date"].strftime("%Y-%m-%d")
        except Exception:
            price_date = target_date

        raw[_dashboard_market(ticker)].append({
            "name": h.get("name", ticker),
            "code": ticker.split(".")[0],
            "ticker": ticker,
            "latest": latest,
            "qty": qty,
            "cost_price": cost_price,
            "market_value": latest * qty,
            "daily_pnl": (latest - prev) * qty if prev is not None else 0.0,
            "daily_pct": ((latest - prev) / prev * 100) if prev not in (None, 0) else None,
            "price_date": price_date,
        })

    currency = {"a-share": "¥", "us": "$"}
    result: dict = {"generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "errors": errors}

    for market, rows in raw.items():
        symbol = currency[market]
        total_value = sum(r["market_value"] for r in rows)
        total_daily_pnl = sum(r["daily_pnl"] for r in rows)
        prev_total = total_value - total_daily_pnl
        change_pct = (total_daily_pnl / prev_total * 100) if prev_total not in (None, 0) else 0.0
        latest_date = max((r["price_date"] for r in rows), default=target_date)

        holdings_list = []
        for r in rows:
            weight = (r["market_value"] / total_value * 100) if total_value else 0.0
            holdings_list.append({
                "name": r["name"],
                "code": r["code"],
                "ticker": r["ticker"],
                "price": f"{r['latest']:,.2f}",
                "change": f"{r['daily_pct']:+.2f}%" if r["daily_pct"] is not None else "—",
                "up": r["daily_pct"] is None or r["daily_pct"] >= 0,
                "weight": f"{weight:.1f}%",
                "quantity": int(r["qty"]) if r["qty"].is_integer() else r["qty"],
                "costPrice": round(r["cost_price"], 4),
                "marketValue": round(r["market_value"], 2),
                "dailyPnl": round(r["daily_pnl"], 2),
                "dailyPnlPercent": (
                    f"{r['daily_pct']:+.2f}%" if r["daily_pct"] is not None else "—"
                ),
                "positionPnl": (
                    round((r["latest"] - r["cost_price"]) * r["qty"], 2)
                    if r["cost_price"]
                    else None
                ),
                "positionPnlPercent": (
                    f"{(r['latest'] / r['cost_price'] - 1) * 100:+.2f}%"
                    if r["cost_price"]
                    else "—"
                ),
                "priceDate": r["price_date"],
            })

        result[market] = {
            "portfolio": {
                "total": f"{symbol}{total_value:,.2f}",
                "changeAmount": _fmt_currency_signed(total_daily_pnl, symbol),
                "changePercent": f"{change_pct:+.2f}%",
                "up": total_daily_pnl >= 0,
                "totalValue": round(total_value, 2),
                "dailyPnl": round(total_daily_pnl, 2),
                "date": latest_date,
            },
            "holdings": holdings_list,
        }

    return result


@app.route("/api/dashboard/portfolio")
def api_dashboard_portfolio():
    """Serve real portfolio overview data for the dashboard panel."""
    try:
        return jsonify(_build_dashboard_portfolio())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def _build_dashboard_stock(ticker: str, candle_days: int | None = None) -> dict:
    """Build stock detail (latest quote + OHLCV candles) for the dashboard panel.

    Candles come straight from the SQLite OHLCV cache; ``candle_days`` limits the
    row count (None returns the full cached history). Each candle also carries
    derived tooltip metrics (change/changePct/amplitude/turnover). The response
    includes trade markers (buy/sell), per-date trade details for the tooltip,
    and the holding's average cost price for the cost line — mirroring the
    summary page's ``_build_lightweight_chart`` behaviour.
    """
    target_date = datetime.now().strftime("%Y-%m-%d")
    df = _get_price_history(ticker, CACHE_DIR, target_date, days=candle_days)
    if df is None or df.empty:
        raise LookupError(f"No cached price for {ticker}")

    name = ticker
    cost_price: float | None = None
    for h in _load_holdings(HOLDINGS_PATH):
        if h.get("ticker") == ticker:
            name = h.get("name", ticker)
            raw_cost = h.get("cost_price")
            if isinstance(raw_cost, (int, float)) and not math.isnan(raw_cost) and raw_cost > 0:
                cost_price = round(float(raw_cost), 4)
            break

    candles = []
    prev_close: float | None = None
    for _, row in df.iterrows():
        try:
            time_str = row["Date"].strftime("%Y-%m-%d")
        except Exception:
            continue
        try:
            o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
        except (TypeError, ValueError):
            continue
        # Skip rows with missing OHLC values (NaN != NaN) so the JSON stays valid.
        if math.isnan(o) or math.isnan(h) or math.isnan(l) or math.isnan(c):
            continue
        v = int(row["Volume"]) if row.get("Volume") == row.get("Volume") else 0
        change = (c - prev_close) if prev_close is not None else None
        candles.append({
            "time": time_str,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
            "change": round(change, 4) if change is not None else None,
            "changePct": round(change / prev_close * 100, 4) if change is not None and prev_close else None,
            "amplitude": round((h - l) / prev_close * 100, 4) if prev_close else None,
            "turnover": round(v * c, 4) if v else None,
        })
        prev_close = c

    if not candles:
        raise LookupError(f"No valid OHLCV rows for {ticker}")

    latest = candles[-1]["close"]
    prev = candles[-2]["close"] if len(candles) > 1 else None
    change_amount = latest - prev if prev is not None else None
    change_pct = (change_amount / prev * 100) if prev not in (None, 0) else None

    # Buy/sell markers plus per-date details for the crosshair tooltip
    # (same aggregation rules as the summary page's chart).
    transactions = _load_transactions(TRANSACTIONS_PATH)
    aggregated = _aggregate_trades(transactions.get(ticker, [])) if transactions else {}
    markers = []
    trades_by_date: dict[str, list[dict]] = {}
    for date, day_trades in aggregated.items():
        entries = []
        for side in ("buy", "sell"):
            entry = day_trades.get(side)
            if not entry or entry["qty"] <= 0:
                continue
            avg_price = round(entry["amount"] / entry["qty"], 4) if entry["qty"] else 0
            markers.append({
                "time": date,
                "position": "belowBar" if side == "buy" else "aboveBar",
                "color": "#ef4444" if side == "buy" else "#10b981",
                "shape": "arrowUp" if side == "buy" else "arrowDown",
                "text": "B" if side == "buy" else "S",
                "size": 2,
            })
            entries.append({"side": side, "qty": entry["qty"], "avgPrice": avg_price})
        if entries:
            trades_by_date[date] = entries
    markers.sort(key=lambda m: m["time"])

    return {
        "ticker": ticker,
        "name": name,
        "code": ticker.split(".")[0],
        "price": f"{latest:,.2f}",
        "latest": latest,
        "prevClose": prev,
        "changeAmount": f"{change_amount:+,.2f}" if change_amount is not None else None,
        "changePercent": f"{change_pct:+.2f}%" if change_pct is not None else None,
        "up": change_amount is None or change_amount >= 0,
        "priceDate": candles[-1]["time"] if candles else target_date,
        "candles": candles,
        "markers": markers,
        "tradesByDate": trades_by_date,
        "costPrice": cost_price,
    }


@app.route("/api/dashboard/stock/<ticker>")
def api_dashboard_stock(ticker: str):
    """Serve OHLCV candles and latest quote for the dashboard stock panel."""
    try:
        return jsonify(_build_dashboard_stock(ticker))
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


_DOW_NAMES = ["一", "二", "三", "四", "五", "六", "日"]
_VALID_RATINGS = {"Buy", "Overweight", "Hold", "Underweight", "Sell"}


def _report_dirs_by_date(ticker: str, dates: list[str]) -> dict[str, str]:
    """Map each calendar date to the latest report directory name for a ticker.

    Directory names sort chronologically (``YYYY-MM-DD_HHMMSS``), so the max
    name wins when several reports exist for the same date — matching the
    "latest report" rule used by ``_get_recent_signals``.
    """
    ticker_dir = REPORTS_DIR / ticker
    if not ticker_dir.exists():
        return {}
    wanted = set(dates)
    latest: dict[str, str] = {}
    for d in ticker_dir.iterdir():
        if not d.is_dir() or d.name[:10] not in wanted:
            continue
        if not (d / "complete_report.md").exists():
            continue
        day = d.name[:10]
        if day not in latest or d.name > latest[day]:
            latest[day] = d.name
    return latest


def _build_dashboard_matrix(target_date: str | None = None, days: int = 15) -> dict:
    """Build the N-day signal backtest matrix for the dashboard panel.

    Combines PM ratings from reports (``_get_recent_signals``, five-level
    Buy/Overweight/Hold/Underweight/Sell) with close-to-close returns after
    each signal day (``_get_signal_outcomes``, offsets [1, 2, 3, 7] plus the
    latest trading day) so the frontend can render rating cells with a
    T+1/T+2/T+3 outcome strip, mirroring the portfolio summary page.

    Weekends are dropped from the calendar-day window (markets closed) and
    report dates are exposed so the frontend can offer a date picker.
    """
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
    holdings = _load_holdings(HOLDINGS_PATH)

    # Calendar days, newest -> oldest, without weekends.
    dates = [
        d for d in _recent_dates(target_date, days)
        if datetime.strptime(d, "%Y-%m-%d").weekday() < 5
    ]
    trading_days = []
    for d in dates:
        dt = datetime.strptime(d, "%Y-%m-%d")
        trading_days.append({"date": d[5:], "dow": _DOW_NAMES[dt.weekday()], "fullDate": d})

    outcome_keys = ["ret1", "ret2", "ret3", "ret7", "retLatest"]
    matrix: dict[str, list[dict]] = {}
    for h in holdings:
        ticker = h["ticker"]
        code = ticker.split(".")[0]

        sig_by_date = {s["date"]: s["rating"] for s in _get_recent_signals(ticker, REPORTS_DIR, target_date, days)}
        outcomes_by_date = _get_signal_outcomes(ticker, CACHE_DIR, target_date, days)
        report_dirs = _report_dirs_by_date(ticker, dates)

        row: list[dict] = []
        for d in dates:
            dt = datetime.strptime(d, "%Y-%m-%d")
            raw_rating = sig_by_date.get(d, "X")
            rating = raw_rating if raw_rating in _VALID_RATINGS else None
            entry: dict = {
                "date": d[5:],
                "dow": _DOW_NAMES[dt.weekday()],
                "fullDate": d,
                "rating": rating,
                "reportDir": report_dirs.get(d),
            }

            if rating:
                # outcomes: [(daily, cumulative)] for offsets [1, 2, 3, 7] + latest.
                rets = outcomes_by_date.get(d) or []
                for i, key in enumerate(outcome_keys):
                    daily, cum = rets[i] if i < len(rets) else (None, None)
                    entry[key] = None if daily is None else round(daily, 2)
                    entry["cum" + key[3:]] = None if cum is None else round(cum, 2)
            row.append(entry)
        matrix[code] = row

    return {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "selectedDate": target_date,
        "availableDates": _available_dates()[:30],
        "tradingDays": trading_days,
        "matrix": matrix,
    }


@app.route("/api/dashboard/matrix")
def api_dashboard_matrix():
    """Serve the 15-day rating backtest matrix for the dashboard panel."""
    try:
        return jsonify(_build_dashboard_matrix(request.args.get("date") or None))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# Role -> (display name, report-relative file) for the bottom analysis cards.
_ROLE_FILES = [
    ("market", "市场分析师", "1_analysts/market.md"),
    ("fundamentals", "基本面分析师", "1_analysts/fundamentals.md"),
    ("news", "新闻分析师", "1_analysts/news.md"),
    ("trader", "交易员", "3_trading/trader.md"),
    ("pm", "组合经理", "5_portfolio/decision.md"),
]

_ROLE_RATING_PATTERNS = {
    "market": [r"FINAL TRANSACTION PROPOSAL:?\s*\*{0,2}(\w+)"],
    "fundamentals": [r"FINAL TRANSACTION PROPOSAL:?\s*\*{0,2}(\w+)"],
    "news": [r"FINAL TRANSACTION PROPOSAL:?\s*\*{0,2}(\w+)"],
    "trader": [r"\*\*Action\*\*:?\s*\*{0,2}(\w+)", r"FINAL TRANSACTION PROPOSAL:?\s*\*{0,2}(\w+)"],
    "pm": [r"\*\*Rating\*\*:?\s*\*{0,2}(\w+)"],
}

_RATING_RANKS = {"Buy": 2, "Overweight": 1, "Hold": 0, "Underweight": -1, "Sell": -2}
_SENTIMENT_THRESHOLDS = [(2, "极度恐惧"), (4, "恐惧"), (6, "中立"), (8, "贪婪"), (10.01, "极度贪婪")]


def _extract_role_rating(text: str, patterns: list[str]) -> str | None:
    """Return the first valid five-level rating matched by any pattern."""
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            rating = match.group(1).strip().capitalize()
            if rating in _VALID_RATINGS:
                return rating
    return None


def _latest_report_dir(ticker: str) -> Path | None:
    """Locate the latest dated report snapshot containing a PM decision."""
    ticker_dir = REPORTS_DIR / ticker
    if not ticker_dir.exists():
        return None
    candidates = [
        d for d in ticker_dir.iterdir()
        if d.is_dir()
        and re.match(r"^\d{4}-\d{2}-\d{2}_", d.name)
        and (d / "5_portfolio" / "decision.md").exists()
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda d: d.name)[-1]


# Memoized Chanlun summaries keyed by (ticker, anchor date): the structure
# only changes with new bars, so compute once per ticker per day.
_chanlun_summary_memo: dict[tuple[str, str], dict | None] = {}


def _extract_chanlun_summary(cd) -> dict | None:
    """Distill a computed Chanlun structure into dashboard card fields."""
    bis = cd.get_bis()
    if not bis:
        return None
    last_bi = bis[-1]
    zss = cd.get_bi_zss()

    # Latest buy/sell point: the most recent line (bi or xd) carrying an MMD.
    mmd = None
    mmd_date = None
    lines = sorted(
        list(bis[-9:]) + list(cd.get_xds()[-3:]),
        key=lambda line: line.end.k.date,
        reverse=True,
    )
    for line in lines:
        codes = cd.get_line_mmds(line)
        if codes:
            mmd = codes
            mmd_date = f"{line.end.k.date:%Y-%m-%d}"
            break

    trend = cd.zss_is_qs(zss[-2], zss[-1]) if len(zss) >= 2 else None
    last_zs = zss[-1] if zss else None
    last_bar = cd.get_src_klines()[-1]
    return {
        "dataDate": f"{last_bar.date:%Y-%m-%d}",
        "close": round(float(last_bar.c), 2),
        "biDirection": last_bi.type,
        "biDone": bool(last_bi.is_done()),
        "biStart": f"{last_bi.start.k.date:%Y-%m-%d}",
        "trend": trend,
        "mmd": mmd,
        "mmdDate": mmd_date,
        "bc": cd.get_line_bcs(last_bi) or None,
        "zsZD": round(float(last_zs.zd), 2) if last_zs else None,
        "zsZG": round(float(last_zs.zg), 2) if last_zs else None,
    }


def _build_chanlun_summary(ticker: str) -> dict | None:
    """Compute a live Chanlun (Chan Theory) structure summary for a ticker.

    Reuses the optional chanlun-core package and the shared OHLCV SQLite cache
    behind the Chanlun Analyst tool. Anchored to yesterday's local date so the
    anchor never resolves to an intraday partial bar. Returns ``None`` when
    chanlun-core is unavailable or the structure cannot be computed, letting
    the dashboard card degrade gracefully.
    """
    from tradingagents.agents.utils import chanlun_tools

    chanlun_core = chanlun_tools._import_chanlun_core()
    if chanlun_core is None:
        return None

    curr_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    memo_key = (ticker, curr_date)
    if memo_key in _chanlun_summary_memo:
        return _chanlun_summary_memo[memo_key]

    summary = None
    try:
        data = chanlun_tools.load_ohlcv(ticker, curr_date)
        if data is not None and len(data) >= chanlun_tools._MIN_BARS:
            klines = pd.DataFrame(
                {
                    "date": pd.to_datetime(data["Date"]),
                    "open": data["Open"].astype(float),
                    "high": data["High"].astype(float),
                    "low": data["Low"].astype(float),
                    "close": data["Close"].astype(float),
                    "volume": data["Volume"].astype(float),
                }
            )
            summary = _extract_chanlun_summary(chanlun_core.analyse(klines))
    except Exception:  # noqa: BLE001 — any failure degrades to "no data"
        summary = None

    _chanlun_summary_memo[memo_key] = summary
    return summary


def _build_dashboard_analysis(ticker: str) -> dict:
    """Build the bottom analysis cards for a ticker from its latest report.

    - sentiment: averaged five-level ratings across analyst/trader/PM roles,
      mapped onto a 0-10 gauge score (0 extreme fear, 10 extreme greed)
    - analyst: TradingView TA cached vote split (bull vs bear share)
    - chanlun: live Chan Theory structure summary (bi direction / pivot zone /
      trend / buy-sell points) computed from the shared OHLCV cache
    """
    report_dir = _latest_report_dir(ticker)
    if report_dir is None:
        raise LookupError(f"No analysis report found for {ticker}")
    report_date = report_dir.name[:10]

    roles = []
    for key, role_name, rel_path in _ROLE_FILES:
        path = report_dir / rel_path
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rating = _extract_role_rating(text, _ROLE_RATING_PATTERNS[key])
        if rating:
            roles.append({"role": key, "roleName": role_name, "rating": rating, "rank": _RATING_RANKS[rating]})

    sentiment = None
    if roles:
        avg_rank = sum(r["rank"] for r in roles) / len(roles)
        score = round((avg_rank + 2) / 4 * 10, 1)
        label = _SENTIMENT_THRESHOLDS[-1][1]
        for threshold, lb in _SENTIMENT_THRESHOLDS:
            if score < threshold:
                label = lb
                break
        sentiment = {
            "score": score,
            "label": label,
            "angle": round(score * 9 - 45, 1),
            "roles": roles,
        }

    analyst = None
    ta = _load_ta_for_report(ticker, report_date)
    if ta and ta.get("data"):
        ta_data = ta["data"]
        buy = int(ta_data.get("buy_votes") or 0)
        sell = int(ta_data.get("sell_votes") or 0)
        total = buy + sell
        bull = round(buy / total * 100, 1) if total else 50.0
        analyst = {
            "bull": bull,
            "bear": round(100 - bull, 1),
            "recommendation": ta_data.get("recommendation"),
            "buyVotes": buy,
            "sellVotes": sell,
            "neutralVotes": int(ta_data.get("neutral_votes") or 0),
            "taDate": ta.get("date"),
        }

    chanlun = _build_chanlun_summary(ticker)

    return {
        "ticker": ticker,
        "reportDate": report_date,
        "reportDir": report_dir.name,
        "sentiment": sentiment,
        "analyst": analyst,
        "chanlun": chanlun,
    }


@app.route("/api/dashboard/analysis/<ticker>")
def api_dashboard_analysis(ticker):
    """Serve the bottom analysis cards data for the dashboard panel."""
    try:
        return jsonify(_build_dashboard_analysis(ticker))
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/reports")
def api_reports():
    return jsonify(scan_reports(REPORTS_DIR))


@app.route("/api/report/<ticker>/<date_time>/__files__")
def api_report_files(ticker, date_time):
    return jsonify(list_report_files(REPORTS_DIR, ticker, date_time))


@app.route("/api/report/<ticker>/<date_time>/<path:file_path>")
def api_report_file(ticker, date_time, file_path):
    target = REPORTS_DIR / ticker / date_time / file_path
    try:
        target.resolve().relative_to(REPORTS_DIR.resolve())
    except ValueError:
        return "Forbidden", 403
    if target.exists() and target.is_file():
        content = target.read_text(encoding="utf-8")
        return content, 200, {"Content-Type": "text/markdown; charset=utf-8"}
    return "Not found", 404


def _load_ta_for_report(ticker: str, date: str) -> dict | None:
    """Load TradingView TA from cache for ``date``, falling back to latest cached date."""
    data = tradingview_ta_cache.load_ta(ticker, date)
    if data is not None:
        return {"date": date, "fallback": False, "data": data}

    try:
        rows = tradingview_ta_cache._get_connection().execute(
            "SELECT date FROM tradingview_ta WHERE symbol = ? ORDER BY date DESC LIMIT 1",
            (tradingview_ta_cache._normalize_symbol(ticker),),
        ).fetchall()
        if rows:
            fallback_date = rows[0]["date"]
            data = tradingview_ta_cache.load_ta(ticker, fallback_date)
            if data is not None:
                return {"date": fallback_date, "fallback": True, "data": data}
    except Exception:
        pass
    return None


@app.route("/api/ta/<ticker>/<date>")
def api_ta(ticker, date):
    result = _load_ta_for_report(ticker, date)
    if result is None:
        return jsonify({"error": "No TradingView TA data found"}), 404
    return jsonify(result)


@app.route("/", methods=["GET"])
def index():
    available_dates = _available_dates()
    selected_date = request.args.get("date")

    if not selected_date:
        selected_date = datetime.now().strftime("%Y-%m-%d")

    # Fall back to the latest available date if the selected date has no reports
    if selected_date not in available_dates and available_dates:
        earlier = [d for d in available_dates if d <= selected_date]
        selected_date = earlier[0] if earlier else available_dates[0]

    df, errors = build_summary_data(
        holdings_path=HOLDINGS_PATH,
        reports_dir=REPORTS_DIR,
        cache_dir=CACHE_DIR,
        target_date=selected_date,
        days=DAYS,
    )

    transactions = _load_transactions(TRANSACTIONS_PATH)
    cards_html = _build_cards_html(
        df=df,
        cache_dir=CACHE_DIR,
        target_date=selected_date,
        reports_dir=REPORTS_DIR,
        report_server_url=REPORT_SERVER_URL,
        transactions=transactions,
    ) if not df.empty else ""

    return render_template_string(
        _PAGE_TEMPLATE,
        available_dates=available_dates,
        selected_date=selected_date,
        cards_html=cards_html,
        styles=_base_styles(),
        errors=errors,
    )


def main():
    parser = argparse.ArgumentParser(description="Portfolio summary web server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=5000, help="Bind port")
    parser.add_argument("--holdings", help="Path to portfolio holdings JSON")
    parser.add_argument("--reports-dir", help="Path to reports directory")
    parser.add_argument("--cache-dir", help="Path to cache directory")
    parser.add_argument("--report-server-url", help="Base URL of the report server for detail links")
    args = parser.parse_args()

    global HOLDINGS_PATH, REPORTS_DIR, CACHE_DIR, REPORT_SERVER_URL
    if args.holdings:
        HOLDINGS_PATH = Path(args.holdings)
    if args.reports_dir:
        REPORTS_DIR = Path(args.reports_dir)
    if args.cache_dir:
        CACHE_DIR = Path(args.cache_dir)
    if args.report_server_url:
        REPORT_SERVER_URL = args.report_server_url

    print(f"Starting portfolio summary server at http://{args.host}:{args.port}")
    print(f"Reports dir: {REPORTS_DIR}")
    print(f"Holdings:    {HOLDINGS_PATH}")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
