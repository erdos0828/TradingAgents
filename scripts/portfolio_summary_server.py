#!/usr/bin/env python3
"""Dynamic portfolio summary web server.

Serves an HTML page that lets the user pick a date and generates the portfolio
summary on demand by scanning reports/{ticker}/{date}_{time}/ directories.

Usage:
    .venv/bin/python -m scripts.portfolio_summary_server
    .venv/bin/python -m scripts.portfolio_summary_server --port 8080
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template_string, request

# Make sibling modules importable when running as `python -m scripts.xxx`
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from report_server import INDEX_HTML, list_report_files, scan_reports
from send_portfolio_summary import (
    _base_styles,
    _build_cards_html,
    _load_transactions,
    build_summary_data,
)

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
    <style>
        header {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 24px;
            flex-wrap: wrap;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 2px solid var(--border);
        }
        .controls {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        label { font-weight: 600; font-size: 14px; }
        select {
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 14px;
            background: #fff;
            min-width: 140px;
        }
        button {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            background: var(--accent);
            color: #fff;
            font-size: 14px;
            cursor: pointer;
        }
        button:hover { background: #2980b9; }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--muted);
            background: var(--card-bg);
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>持仓分析汇总</h1>
                <div class="meta">动态生成 &nbsp;|&nbsp; 基于 reports/ 目录自动汇总</div>
            </div>
            <form class="controls" method="get" action="/">
                <label for="date">选择日期：</label>
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
</body>
</html>
"""


@app.route("/reports")
def report_index():
    """Serve the detailed report browser (merged from report_server.py)."""
    return Response(INDEX_HTML, mimetype="text/html; charset=utf-8")


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
    cards_html = _build_cards_html(df, CACHE_DIR, selected_date, REPORT_SERVER_URL, transactions) if not df.empty else ""

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
