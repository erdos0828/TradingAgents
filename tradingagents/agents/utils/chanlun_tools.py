"""Chanlun (Chan Theory) structural analysis tool for TradingAgents.

Wraps the optional local ``chanlun-core`` package to expose the Chan-theory
structure (bi strokes / xd segments / pivots / buy-sell points / divergences)
computed from the shared SQLite OHLCV cache — the same data the Market
Analyst's indicators use, so look-ahead protection is inherited for free.

The package is an optional dependency (``pip install ".[chanlun]"`` or a
sibling checkout), so it is imported lazily: when unavailable the tool
returns a clear error string instead of crashing the analyst run.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Annotated

import pandas as pd
from langchain_core.tools import tool

from tradingagents.dataflows.stockstats_utils import load_ohlcv

logger = logging.getLogger(__name__)

# Chanlun structure detection needs a few up/down alternations at minimum;
# anything shorter produces a meaningless zig-zag.
_MIN_BARS = 60

_MMD_LABELS = {
    "1buy": "1st buy",
    "2buy": "2nd buy",
    "3buy": "3rd buy",
    "l2buy": "like-2nd buy",
    "l3buy": "like-3rd buy",
    "1sell": "1st sell",
    "2sell": "2nd sell",
    "3sell": "3rd sell",
    "l2sell": "like-2nd sell",
    "l3sell": "like-3rd sell",
}
_BC_LABELS = {
    "bi": "bi divergence",
    "xd": "segment divergence",
    "pz": "consolidation divergence",
    "qs": "trend divergence",
}
_ZS_TYPE_LABELS = {"up": "up pivot", "down": "down pivot", "zd": "range pivot"}
_ZS_QS_LABELS = {
    "up": "uptrend (pivots do not overlap)",
    "down": "downtrend (pivots do not overlap)",
    None: "overlapping pivots (extension)",
}


def _import_chanlun_core():
    """Import chanlun-core, falling back to local checkouts.

    Resolution order: installed package -> ``TRADINGAGENTS_CHANLUN_CORE_PATH``
    -> sibling ``../chanlun-core/src`` next to this project's checkout.
    Returns ``None`` when the package cannot be resolved anywhere.
    """
    try:
        import chanlun_core

        return chanlun_core
    except ImportError:
        pass

    candidates = []
    env_path = os.environ.get("TRADINGAGENTS_CHANLUN_CORE_PATH")
    if env_path:
        candidates.append(Path(env_path).expanduser())
    # <project_root>/../chanlun-core/src — the sibling-checkout layout used
    # by the pyproject "chanlun" extra.
    project_root = Path(__file__).resolve().parents[3]
    candidates.append(project_root.parent / "chanlun-core" / "src")

    for cand in candidates:
        if (cand / "chanlun_core" / "__init__.py").exists():
            sys.path.insert(0, str(cand))
            try:
                import chanlun_core

                return chanlun_core
            except ImportError as exc:
                logger.warning(
                    "chanlun-core found at %s but not importable: %s", cand, exc
                )
    return None


def _join_labels(raw: str, mapping: dict[str, str]) -> str:
    """Map a pipe-joined code list (e.g. ``1buy|3buy``) to readable labels."""
    names = [n for n in raw.split("|") if n]
    labels = sorted(mapping.get(n, n) for n in names)
    return "|".join(labels) if labels else "-"


def _format_chanlun_result(cd, ticker: str, curr_date: str) -> str:
    """Render the Chanlun structure as a Markdown payload for the analyst."""
    k = cd.get_src_klines()[-1]
    lines = [
        f"Chanlun (Chan Theory) structure for {ticker} (daily bars), as of {curr_date}.",
        f"Latest bar: {k.date:%Y-%m-%d} close={k.c:.2f}",
        "",
        "## Bi (strokes) — latest 9",
        "| start date | end date | direction | start val | end val | done | buy/sell points | divergences |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    for bi in cd.get_bis()[-9:]:
        lines.append(
            f"| {bi.start.k.date:%Y-%m-%d} | {bi.end.k.date:%Y-%m-%d} | {bi.type} "
            f"| {bi.start.val:.2f} | {bi.end.val:.2f} "
            f"| {'yes' if bi.is_done() else 'no'} "
            f"| {_join_labels(cd.get_line_mmds(bi), _MMD_LABELS)} "
            f"| {_join_labels(cd.get_line_bcs(bi), _BC_LABELS)} |"
        )

    lines += [
        "",
        "## XD (segments) — latest 3",
        "| start date | end date | direction | start val | end val | done | buy/sell points | divergences |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    for xd in cd.get_xds()[-3:]:
        lines.append(
            f"| {xd.start.k.date:%Y-%m-%d} | {xd.end.k.date:%Y-%m-%d} | {xd.type} "
            f"| {xd.start.val:.2f} | {xd.end.val:.2f} "
            f"| {'yes' if xd.is_done() else 'no'} "
            f"| {_join_labels(cd.get_line_mmds(xd), _MMD_LABELS)} "
            f"| {_join_labels(cd.get_line_bcs(xd), _BC_LABELS)} |"
        )

    lines += [
        "",
        "## Bi-level pivots (zhongshu) — latest 2",
        "| start date | end date | direction | GG (high) | DD (low) | ZG (zone high) | ZD (zone low) | level |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    for zs in cd.get_bi_zss()[-2:]:
        lines.append(
            f"| {zs.start.k.date:%Y-%m-%d} | {zs.end.k.date:%Y-%m-%d} "
            f"| {_ZS_TYPE_LABELS.get(zs.type, zs.type)} "
            f"| {zs.gg:.2f} | {zs.dd:.2f} | {zs.zg:.2f} | {zs.zd:.2f} | {zs.level} |"
        )

    zss = cd.get_bi_zss()
    if len(zss) >= 2:
        relation = cd.zss_is_qs(zss[-2], zss[-1])
        lines += ["", f"Relationship of the last two pivots: **{_ZS_QS_LABELS.get(relation, relation)}**."]
    elif zss:
        lines += ["", "Only one bi-level pivot formed so far."]

    lines += [
        "",
        "Notes:",
        "- bi = stroke (zig-zag between consecutive top/bottom fractals); xd = segment (at least 3 bi).",
        "- Pivot ZG/ZD = overlap zone of the first three sub-lines; GG/DD = highest/lowest reached inside the pivot.",
        "- Buy/sell points: 1st = after a trend divergence; 2nd = first pullback after a 1st point; 3rd = pullback that leaves the pivot without re-entering. \"like-\" variants are weaker analogues.",
        "- done=no means the line is still forming and its endpoint may still move.",
        "- level>0 means the pivot subsumes more than 9 sub-lines (level upgrade).",
    ]
    return "\n".join(lines)


@tool
def get_chanlun_analysis(
    symbol: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
) -> str:
    """Compute the Chan Theory (Chanlun) structure for a ticker on daily bars.

    Returns the latest bi strokes, xd segments and bi-level pivots with their
    buy/sell points and divergences, derived from the same cached OHLCV data
    the other analysts use (so no look-ahead bias). When the optional
    chanlun-core package is not installed, returns an explicit unavailable
    message instead of raising, so the analyst can report it gracefully.
    """
    chanlun_core = _import_chanlun_core()
    if chanlun_core is None:
        return (
            "Chanlun analysis is unavailable: the optional chanlun-core package "
            'is not installed. Install it via `pip install ".[chanlun]"` or set '
            "TRADINGAGENTS_CHANLUN_CORE_PATH to a chanlun-core/src checkout."
        )

    try:
        data = load_ohlcv(symbol, curr_date)
    except Exception as exc:  # noqa: BLE001 — surface data errors to the LLM
        logger.warning("Chanlun tool could not load OHLCV for %s: %s", symbol, exc)
        return f"Chanlun analysis failed while loading OHLCV for {symbol}: {exc}"

    if data is None or len(data) < _MIN_BARS:
        got = 0 if data is None else len(data)
        return (
            f"Chanlun analysis needs at least {_MIN_BARS} daily bars for {symbol}; "
            f"only {got} available."
        )

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

    try:
        cd = chanlun_core.analyse(klines)
    except Exception as exc:  # noqa: BLE001 — computation errors go to the LLM
        logger.warning("Chanlun computation failed for %s: %s", symbol, exc)
        return f"Chanlun computation failed for {symbol}: {exc}"

    return _format_chanlun_result(cd, symbol, curr_date)
