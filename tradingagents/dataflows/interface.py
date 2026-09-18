import logging

from . import akshare_data
from .alpha_vantage import (
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_global_news as get_alpha_vantage_global_news,
    get_income_statement as get_alpha_vantage_income_statement,
    get_indicator as get_alpha_vantage_indicator,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_stock as get_alpha_vantage_stock,
)
from .config import get_config
from .errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)
from .fred import get_macro_data as get_fred_macro_data
from .polymarket import get_prediction_markets as get_polymarket_prediction_markets
from .tool_response_cache import (
    build_params_key,
    load_response,
    store_response,
)
from .y_finance import (
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_fundamentals as get_yfinance_fundamentals,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
    get_stock_stats_indicators_window,
    get_YFin_data_online,
)
from .yfinance_news import get_global_news_yfinance, get_news_yfinance

logger = logging.getLogger(__name__)

# A-share tools are routed through akshare by default so that Chinese stocks use
# domestic news and macro data instead of U.S.-centric vendors.
_AKSHARE_ROUTED_TOOLS = {
    "get_news",
    "get_global_news",
    "get_macro_indicators",
}


def _is_a_share(ticker: str) -> bool:
    """Return True if the ticker is a mainland China A-share."""
    if not ticker:
        return False
    upper = ticker.upper()
    if upper.endswith((".SS", ".SZ", ".BJ")):
        return True
    # Bare 6-digit numeric codes (common in CLI/programmatic callers) are also
    # treated as A-shares; the akshare implementation strips any suffix.
    stripped = upper.split(".")[0]
    return stripped.isdigit() and len(stripped) == 6


# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    },
    "macro_data": {
        "description": "Macroeconomic indicators (rates, inflation, labor, growth)",
        "tools": [
            "get_macro_indicators",
        ]
    },
    "prediction_markets": {
        "description": "Market-implied probabilities for forward-looking events",
        "tools": [
            "get_prediction_markets",
        ]
    }
}

VENDOR_LIST = [
    "akshare",
    "yfinance",
    "fred",
    "polymarket",
    "alpha_vantage",
]

# Optional enrichment categories. These add macro/event context to the news
# analyst but are not core to a decision, so a vendor failure here degrades to a
# sentinel instead of aborting the run (a bad LLM-supplied indicator, a missing
# key, or a network blip should not crash an analysis over flavour data). Core
# categories (prices, fundamentals, news) still raise so a broken primary is loud.
OPTIONAL_CATEGORIES = {"macro_data", "prediction_markets"}

# Categories whose vendor responses are served from the shared SQLite
# tool-response cache. These tools return plain strings (CSV/Markdown) and
# have no dedicated cache of their own, so repeating an identical call within
# the category TTL reuses the stored response instead of re-hitting the
# external API. core_stock_apis and technical_indicators are excluded on
# purpose: their OHLCV cache in stockstats_utils/sqlite_cache already has
# same-day freshness logic this layer must not bypass.
_RESPONSE_CACHE_CATEGORIES = {
    "news_data",
    "fundamental_data",
    "macro_data",
    "prediction_markets",
}

# Sentinel prefixes that must never be cached: they describe a *failure* to
# fetch, not data, so caching one would pin "no data" for the whole TTL after
# a single network blip.
_UNCACHEABLE_PREFIXES = ("NO_DATA_AVAILABLE", "DATA_UNAVAILABLE")

# Fallback TTL for a cached category without an explicit override.
_DEFAULT_RESPONSE_TTL_SECONDS = 3600

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
    },
    # fundamental_data
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
    },
    # news_data
    "get_news": {
        "akshare": akshare_data.get_news,
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
    },
    "get_global_news": {
        "akshare": akshare_data.get_global_news,
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
    },
    # macro_data
    "get_macro_indicators": {
        "akshare": akshare_data.get_macro_data,
        "fred": get_fred_macro_data,
    },
    # prediction_markets
    "get_prediction_markets": {
        "polymarket": get_polymarket_prediction_markets,
    },
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

def _resolve_vendor_chain(method: str, category: str) -> list[str]:
    """Resolve the ordered vendor chain for ``method`` from the config.

    The configured vendor list IS the chain: we do NOT silently fall back to
    vendors the user did not choose (#988/#289) — that returned data from an
    unexpected source and caused cross-vendor inconsistencies. For multi-vendor
    fallback, list them in order, e.g. data_vendors="yfinance,alpha_vantage".
    The "default" sentinel (no explicit config) uses all available vendors.
    """
    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    all_available_vendors = list(VENDOR_METHODS[method].keys())

    # A-share analyses use akshare for news and China macro by default so that
    # Chinese stocks are analyzed with domestic data rather than U.S. vendors.
    if (
        method in _AKSHARE_ROUTED_TOOLS
        and _is_a_share(get_config().get("analysis_ticker", ""))
        and "akshare" in all_available_vendors
    ):
        return ["akshare"]

    vendor_config = get_vendor(category, method)
    primary_vendors = [v.strip() for v in vendor_config.split(',')]

    explicit = [v for v in primary_vendors if v and v != "default"]
    if explicit:
        vendor_chain = [v for v in explicit if v in VENDOR_METHODS[method]]
        if not vendor_chain:
            raise ValueError(
                f"Configured vendor(s) {explicit} not available for '{method}'. "
                f"Available: {all_available_vendors}."
            )
    else:
        vendor_chain = all_available_vendors
    return vendor_chain


def _dispatch_to_vendors(
    method: str,
    category: str,
    vendor_chain: list[str],
    *args,
    **kwargs,
):
    """Try each vendor in ``vendor_chain`` in order, with typed-error fallback."""
    last_no_data: NoMarketDataError | None = None
    first_error: Exception | None = None
    for vendor in vendor_chain:
        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            return impl_func(*args, **kwargs)
        except VendorRateLimitError:
            logger.warning("Vendor %r rate-limited for %s; trying next vendor.", vendor, method)
            continue
        except VendorNotConfiguredError as e:
            logger.warning("Vendor %r not configured for %s; trying next vendor.", vendor, method)
            if first_error is None:
                first_error = e  # Surface it if no other vendor can serve the call.
            continue
        except NoMarketDataError as e:
            last_no_data = e  # No data here; another configured vendor may have it
            continue
        except Exception as e:
            # Don't let one vendor's failure crash the call when another can
            # serve it, but never swallow silently: a broken primary must be
            # visible in the logs (#989), not hidden behind a fallback's verdict.
            logger.warning("Vendor %r failed for %s: %s", vendor, method, e)
            if first_error is None:
                first_error = e
            continue

    # If any vendor reported "no data", the symbol is genuinely unavailable.
    # Return one explicit, instructive sentinel rather than a vendor-specific
    # empty string, so the agent reports "unavailable" instead of inventing a
    # value. This takes precedence over incidental fallback errors.
    if last_no_data is not None:
        if first_error is not None:
            # A vendor also hit a real error; surface it in logs so the no-data
            # verdict can't hide a broken primary (network/auth/etc.).
            logger.warning(
                "Returning NO_DATA for %s, but a vendor errored earlier: %s",
                method, first_error,
            )
        sym = last_no_data.symbol
        canonical = last_no_data.canonical
        resolved = "" if canonical == sym else f" (resolved to '{canonical}')"
        # Surface the typed error's detail (e.g. "latest row is 2025-06-11 ...
        # stale") so the agent sees the specific reason — invalid symbol, no
        # coverage, or stale data — not just a generic "unavailable".
        reason = f" ({last_no_data.detail})" if last_no_data.detail else ""
        return (
            f"NO_DATA_AVAILABLE: No usable market data for '{sym}'{resolved} from "
            f"any configured vendor{reason}. The symbol may be invalid, delisted, "
            f"not covered, or the vendor returned stale data. Do not estimate or "
            f"fabricate values — report that data is unavailable for this symbol."
        )

    # No vendor returned data and none reported clean "no data" — surface the
    # first real error (e.g. the primary vendor's network failure). Optional
    # enrichment categories degrade to a sentinel instead, so flavour data can't
    # abort the run.
    if first_error is not None:
        if category in OPTIONAL_CATEGORIES:
            logger.warning("Optional %s unavailable for %s: %s", category, method, first_error)
            return (
                f"DATA_UNAVAILABLE: optional {category} could not be retrieved "
                f"({first_error}). Proceed without it; do not fabricate values."
            )
        raise first_error

    raise RuntimeError(f"No available vendor for '{method}'")


def _extract_ticker_and_date() -> tuple[str | None, str | None]:
    """Return the current analysis context for cache metadata.

    The (ticker, date) stored in the tool_response_cache table describe the
    analysis being performed, not the arguments of an individual tool. This
    lets ticker-less tools such as global news, macro indicators, and
    prediction markets still be associated with the ticker and trade date that
    triggered the analysis. Tool-specific arguments are already recorded in
    ``params``/``params_hash``.
    """
    config = get_config()
    return config.get("analysis_ticker"), config.get("analysis_date")


def _cacheable_response(result) -> bool:
    """A response is cacheable only if it is real data, not a failure sentinel."""
    return isinstance(result, str) and not result.startswith(_UNCACHEABLE_PREFIXES)


def _response_cache_ttl_seconds(config: dict, category: str) -> float:
    """Category TTL from config (``tool_cache_ttl_seconds``) with a fallback."""
    ttl_overrides = config.get("tool_cache_ttl_seconds") or {}
    return float(ttl_overrides.get(category, _DEFAULT_RESPONSE_TTL_SECONDS))


def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support.

    Cache-eligible categories (news, fundamentals, macro, prediction markets)
    are served from the shared SQLite tool-response cache when a fresh entry
    exists, and successful responses are stored for reuse within the category
    TTL — so a repeated identical call (agent retries, multi-ticker runs sharing
    ticker-less tools, same-day re-runs) does not re-hit the external API.
    Failure sentinels are never cached, the vendor chain participates in the
    cache key so a config change never serves an unchosen vendor's data, and
    the (ticker, date) dimensions are recorded for cache inspection/pruning.
    """
    category = get_category_for_method(method)
    vendor_chain = _resolve_vendor_chain(method, category)

    if category not in _RESPONSE_CACHE_CATEGORIES:
        return _dispatch_to_vendors(method, category, vendor_chain, *args, **kwargs)

    config = get_config()
    if not config.get("cache_tool_responses", True):
        return _dispatch_to_vendors(method, category, vendor_chain, *args, **kwargs)

    ttl = _response_cache_ttl_seconds(config, category)
    params_hash, params_repr = build_params_key(method, args, kwargs, vendor_chain)
    cached = load_response(method, params_hash, ttl)
    if cached is not None:
        logger.debug("Tool response cache hit for %s(%s)", method, params_repr)
        return cached

    result = _dispatch_to_vendors(method, category, vendor_chain, *args, **kwargs)

    if _cacheable_response(result):
        ticker, date = _extract_ticker_and_date()
        store_response(ticker, date, method, params_hash, params_repr, result)
    return result
