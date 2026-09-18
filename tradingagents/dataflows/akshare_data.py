"""akshare-based data vendor for A-share news and China macro indicators."""

import logging
from datetime import datetime, timedelta

import akshare as ak

from .config import get_config
from .errors import NoMarketDataError

logger = logging.getLogger(__name__)

# Indicator alias -> (akshare function, title, value column, date column, row filter)
# The value/date columns are used to render a consistent markdown table.
# ``row_filter`` is an optional dict ``{column: required_value}`` for tables
# that contain multiple series (e.g. unemployment breaks down by household
# registration); when present only matching rows are kept.
_MACRO_CHINA_FUNCS = {
    "cpi": ("macro_china_cpi", "中国居民消费价格指数(CPI)", "全国-当月", "月份", None),
    "core_cpi": ("macro_china_cpi", "中国居民消费价格指数(CPI)", "全国-当月", "月份", None),
    "ppi": ("macro_china_ppi", "中国工业生产者出厂价格指数(PPI)", "当月", "月份", None),
    "pmi": ("macro_china_pmi", "中国采购经理人指数(PMI)", "制造业-指数", "月份", None),
    "non_man_pmi": ("macro_china_non_man_pmi", "中国非制造业PMI", "非制造业-指数", "月份", None),
    "gdp": ("macro_china_gdp", "国内生产总值(GDP)", "国内生产总值", "季度", None),
    "real_gdp": ("macro_china_gdp", "国内生产总值(GDP)", "国内生产总值", "季度", None),
    "industrial_production": ("macro_china_gyzjz", "中国规模以上工业增加值", "当月", "月份", None),
    "unemployment_rate": ("macro_china_urban_unemployment", "中国城镇调查失业率", "value", "date", {"item": "全国城镇调查失业率"}),
    "unemployment": ("macro_china_urban_unemployment", "中国城镇调查失业率", "value", "date", {"item": "全国城镇调查失业率"}),
    "m2": ("macro_china_money_supply", "中国货币供应量(M2)", "M2-数量", "月份", None),
    "money_supply": ("macro_china_money_supply", "中国货币供应量(M2)", "M2-数量", "月份", None),
    "lpr": ("macro_china_lpr", "贷款市场报价利率(LPR)", "LPR-1Y", "日期", None),
    "shibor": ("macro_china_shibor_all", "上海银行间同业拆放利率(SHIBOR)", "O/N-定价", "日期", None),
    "retail_sales": ("macro_china_consumer_goods_retail", "中国社会消费品零售总额", "当月", "月份", None),
    "fx_reserves": ("macro_china_fx_reserves_yearly", "中国外汇储备", "今值", "日期", None),
}


def _strip_a_share_suffix(ticker: str) -> str:
    """Return the 6-digit numeric code from tickers like 600006.SS."""
    for suffix in (".SS", ".SZ", ".BJ"):
        if ticker.upper().endswith(suffix):
            return ticker[: -len(suffix)]
    return ticker


def _a_share_code(ticker: str) -> str:
    """Validate and normalize an A-share ticker to a 6-digit code."""
    code = _strip_a_share_suffix(ticker)
    if code.isdigit() and len(code) == 6:
        return code
    raise ValueError(f"'{ticker}' is not a recognized A-share ticker")


def get_news(ticker: str, start_date: str, end_date: str) -> str:
    """Fetch A-share individual stock news from East Money via akshare."""
    code = _a_share_code(ticker)
    resolved = "" if code == ticker else f" (resolved to {code})"
    config = get_config()
    limit = config.get("news_article_limit", 20)

    try:
        df = ak.stock_news_em(symbol=code)
    except Exception as e:
        logger.warning("akshare stock_news_em failed for %s: %s", ticker, e)
        raise NoMarketDataError(ticker, ticker, f"akshare news unavailable: {e}") from e

    if df is None or df.empty:
        raise NoMarketDataError(ticker, ticker, "no news rows returned")

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    # News timestamps include seconds; treat the window as inclusive.
    end_inclusive = end_dt + timedelta(days=1)

    rows = []
    for _, row in df.iterrows():
        pub_time = row.get("发布时间")
        if pub_time:
            try:
                pub_dt = datetime.strptime(str(pub_time), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pub_dt = None
        else:
            pub_dt = None

        if pub_dt is not None and not (start_dt <= pub_dt < end_inclusive):
            continue

        rows.append({
            "title": row.get("新闻标题", "No title"),
            "summary": row.get("新闻内容", ""),
            "source": row.get("文章来源", "Unknown"),
            "pub_time": pub_time,
            "link": row.get("新闻链接", ""),
        })
        if len(rows) >= limit:
            break

    if not rows:
        return f"No news found for {ticker}{resolved} between {start_date} and {end_date}"

    parts = [f"## {ticker}{resolved} News (A-share), from {start_date} to {end_date}:\n\n"]
    for r in rows:
        parts.append(f"### {r['title']} (source: {r['source']}, {r['pub_time']})\n")
        if r["summary"]:
            parts.append(f"{r['summary']}\n")
        if r["link"]:
            parts.append(f"Link: {r['link']}\n")
        parts.append("\n")
    return "".join(parts)


def get_global_news(curr_date: str, look_back_days: int | None = None, limit: int | None = None) -> str:
    """Fetch China/mainland financial headlines from Caixin via akshare."""
    config = get_config()
    if look_back_days is None:
        look_back_days = config.get("global_news_lookback_days", 7)
    if limit is None:
        limit = config.get("global_news_article_limit", 10)

    end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=look_back_days)

    try:
        df = ak.stock_news_main_cx()
    except Exception as e:
        logger.warning("akshare stock_news_main_cx failed: %s", e)
        raise NoMarketDataError("global_news", "global_news", f"akshare global news unavailable: {e}") from e

    if df is None or df.empty:
        raise NoMarketDataError("global_news", "global_news", "no global news rows returned")

    rows = []
    for _, row in df.head(limit).iterrows():
        rows.append({
            "tag": row.get("tag", "市场动态"),
            "summary": row.get("summary", ""),
            "link": row.get("url", ""),
        })

    if not rows:
        return f"No China macro news found between {start_dt.date()} and {curr_date}"

    parts = [f"## China Macro/Financial News, from {start_dt.date()} to {curr_date}:\n\n"]
    for r in rows:
        parts.append(f"### [{r['tag']}] {r['summary']}\n")
        if r["link"]:
            parts.append(f"Link: {r['link']}\n")
        parts.append("\n")
    return "".join(parts)


def _resolve_china_macro_alias(indicator: str) -> tuple:
    """Map an indicator alias to akshare China macro function metadata."""
    key = indicator.strip().lower().replace(" ", "_").replace("-", "_")
    if key in _MACRO_CHINA_FUNCS:
        return _MACRO_CHINA_FUNCS[key]
    # Try partial matches (e.g. "urban_unemployment" -> "unemployment").
    for alias, meta in _MACRO_CHINA_FUNCS.items():
        if alias in key or key in alias:
            return meta
    raise ValueError(
        f"'{indicator}' is not a known China macro alias. "
        f"Available: {', '.join(sorted(set(_MACRO_CHINA_FUNCS.keys())))}"
    )


def _format_window(
    df,
    date_col: str,
    value_col: str,
    end_dt: datetime,
    look_back_days: int,
    row_filter: dict[str, str] | None,
):
    """Filter DataFrame to a trailing window and format the latest rows as markdown."""
    start_dt = end_dt - timedelta(days=look_back_days)

    # Normalize dates for filtering. Some columns use strings like "2026年08月份".
    dates = []
    keep = []
    for _, row in df.iterrows():
        if row_filter is not None:
            if not all(str(row.get(k, "")).strip() == v for k, v in row_filter.items()):
                continue

        raw_date = str(row.get(date_col, ""))
        parsed = None
        for fmt in ("%Y-%m-%d", "%Y%m", "%Y年%m月份", "%Y年%m月"):
            try:
                parsed = datetime.strptime(raw_date, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            continue
        if start_dt <= parsed <= end_dt:
            dates.append(parsed)
            keep.append(row)

    points = [(d.strftime("%Y-%m-%d"), str(row.get(value_col, ""))) for d, row in zip(dates, keep)]
    points = [(d, v) for d, v in points if v and v not in ("nan", "NaN", "None")]
    points.sort(key=lambda x: x[0])
    return points


def get_macro_data(indicator: str, curr_date: str, look_back_days: int | None = None) -> str:
    """Fetch a China macroeconomic series from akshare as formatted markdown."""
    if look_back_days is None:
        look_back_days = 365

    end_dt = datetime.strptime(curr_date, "%Y-%m-%d")

    try:
        func_name, title, value_col, date_col, row_filter = _resolve_china_macro_alias(indicator)
    except ValueError:
        return (
            f"akshare China macro: '{indicator}' is not a known alias. "
            f"Use one of: {', '.join(sorted(set(_MACRO_CHINA_FUNCS.keys())))}."
        )

    try:
        func = getattr(ak, func_name)
        df = func()
    except Exception as e:
        logger.warning("akshare %s failed for indicator %s: %s", func_name, indicator, e)
        raise NoMarketDataError(indicator, indicator, f"akshare macro unavailable: {e}") from e

    if df is None or df.empty:
        raise NoMarketDataError(indicator, indicator, "no macro rows returned")

    points = _format_window(df, date_col, value_col, end_dt, look_back_days, row_filter)

    if not points:
        raise NoMarketDataError(
            indicator, indicator, f"no data in window {curr_date} - {look_back_days}d"
        )

    latest_value = points[-1][1]
    latest_date = points[-1][0]
    first_value = points[0][1]
    first_date = points[0][0]

    try:
        latest_f = float(latest_value)
        first_f = float(first_value)
        change = latest_f - first_f
        pct = (change / first_f * 100) if first_f != 0 else 0.0
        change_str = f"{change:+.4f} ({pct:+.2f}%) from {first_value} ({first_date})"
    except (ValueError, TypeError):
        change_str = f"(change unavailable; window start {first_value} {first_date})"

    lines = [
        f"## akshare China Macro: {title} ({indicator})",
        f"- Source: akshare / {func_name}",
        f"- Window: {curr_date} - {look_back_days}d",
        f"**Latest:** {latest_value} ({latest_date}) | **Change over window:** {change_str}",
        "",
        "| Date | Value |",
        "| --- | --- |",
    ]
    for d, v in points[-20:]:  # cap table rows
        lines.append(f"| {d} | {v} |")
    return "\n".join(lines)
