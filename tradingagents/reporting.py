"""Reusable report-tree writer shared by the CLI and the programmatic API.

Writes a run's per-section markdown (analysts, research, trading, risk,
portfolio) plus a consolidated ``complete_report.md`` under ``save_path``. The
CLI and ``TradingAgentsGraph.save_reports`` both call this, so a headless / API
run produces the same on-disk report tree a CLI run does.
"""

import re
from datetime import datetime
from pathlib import Path


def _extract_rating(text: str) -> tuple[str, str]:
    """Extract rating (Buy/Hold/Sell) and first meaningful sentence from text.

    Returns (rating, summary). Rating defaults to "N/A" if not found.
    """
    if not text:
        return "N/A", ""

    # Try common patterns for rating extraction
    rating = "N/A"
    patterns = [
        r"FINAL TRANSACTION PROPOSAL:\s*\*{0,2}(\w+)\*{0,2}",  # FINAL TRANSACTION PROPOSAL: **HOLD**
        r"\*{0,2}Rating\*{0,2}:\s*\*{0,2}(\w+)\*{0,2}",        # **Rating**: Hold
        r"\*{0,2}Action\*{0,2}:\s*\*{0,2}(\w+)\*{0,2}",        # **Action**: Hold
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            rating = match.group(1).capitalize()
            break

    # Extract first meaningful sentence (skip headers, empty lines, common prefixes)
    summary = ""
    # Prefixes to strip from content lines
    strip_prefixes = [
        "**Reasoning**:", "**Executive Summary**:", "**Investment Thesis**:",
        "**Stop Loss**:", "**Position Sizing**:", "**Time Horizon**:",
        "FINAL TRANSACTION PROPOSAL:",
    ]
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        # Skip empty lines, headers
        if not line or line.startswith("#"):
            continue
        # Skip lines that are just rating markers
        if line.startswith("FINAL TRANSACTION") or line.startswith("**Rating**") or line.startswith("**Action**"):
            continue
        # Strip known prefixes
        for prefix in strip_prefixes:
            if line.startswith(prefix):
                line = line[len(prefix):].strip()
                break
        # Skip if line is still empty after stripping
        if not line:
            continue
        # Found a content line - use it as summary
        # Truncate if too long
        summary = line if len(line) <= 150 else line[:147] + "..."
        break

    return rating, summary


def write_report_tree(final_state: dict, ticker: str, save_path) -> Path:
    """Save a completed run's reports to ``save_path``; return the complete-report path."""
    save_path = Path(save_path)
    save_path.mkdir(parents=True, exist_ok=True)
    sections = []
    ratings = []  # Collect (role, rating, summary) for executive summary

    # 1. Analysts
    analysts_dir = save_path / "1_analysts"
    analyst_parts = []
    if final_state.get("market_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "market.md").write_text(final_state["market_report"], encoding="utf-8")
        analyst_parts.append(("Market Analyst", final_state["market_report"]))
        rating, summary = _extract_rating(final_state["market_report"])
        ratings.append(("Market Analyst", rating, summary))
    if final_state.get("sentiment_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "sentiment.md").write_text(final_state["sentiment_report"], encoding="utf-8")
        analyst_parts.append(("Sentiment Analyst", final_state["sentiment_report"]))
        rating, summary = _extract_rating(final_state["sentiment_report"])
        ratings.append(("Sentiment Analyst", rating, summary))
    if final_state.get("news_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "news.md").write_text(final_state["news_report"], encoding="utf-8")
        analyst_parts.append(("News Analyst", final_state["news_report"]))
        rating, summary = _extract_rating(final_state["news_report"])
        ratings.append(("News Analyst", rating, summary))
    if final_state.get("fundamentals_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "fundamentals.md").write_text(final_state["fundamentals_report"], encoding="utf-8")
        analyst_parts.append(("Fundamentals Analyst", final_state["fundamentals_report"]))
        rating, summary = _extract_rating(final_state["fundamentals_report"])
        ratings.append(("Fundamentals Analyst", rating, summary))
    if analyst_parts:
        content = "\n\n".join(f"### {name}\n{text}" for name, text in analyst_parts)
        sections.append(f"## I. Analyst Team Reports\n\n{content}")

    # 2. Research
    if final_state.get("investment_debate_state"):
        research_dir = save_path / "2_research"
        debate = final_state["investment_debate_state"]
        research_parts = []
        if debate.get("bull_history"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "bull.md").write_text(debate["bull_history"], encoding="utf-8")
            research_parts.append(("Bull Researcher", debate["bull_history"]))
        if debate.get("bear_history"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "bear.md").write_text(debate["bear_history"], encoding="utf-8")
            research_parts.append(("Bear Researcher", debate["bear_history"]))
        if debate.get("judge_decision"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "manager.md").write_text(debate["judge_decision"], encoding="utf-8")
            research_parts.append(("Research Manager", debate["judge_decision"]))
            rating, summary = _extract_rating(debate["judge_decision"])
            ratings.append(("Research Manager", rating, summary))
        if research_parts:
            content = "\n\n".join(f"### {name}\n{text}" for name, text in research_parts)
            sections.append(f"## II. Research Team Decision\n\n{content}")

    # 3. Trading
    if final_state.get("trader_investment_plan"):
        trading_dir = save_path / "3_trading"
        trading_dir.mkdir(exist_ok=True)
        (trading_dir / "trader.md").write_text(final_state["trader_investment_plan"], encoding="utf-8")
        sections.append(f"## III. Trading Team Plan\n\n### Trader\n{final_state['trader_investment_plan']}")
        rating, summary = _extract_rating(final_state["trader_investment_plan"])
        ratings.append(("Trader", rating, summary))

    # 4. Risk Management
    if final_state.get("risk_debate_state"):
        risk_dir = save_path / "4_risk"
        risk = final_state["risk_debate_state"]
        risk_parts = []
        if risk.get("aggressive_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "aggressive.md").write_text(risk["aggressive_history"], encoding="utf-8")
            risk_parts.append(("Aggressive Analyst", risk["aggressive_history"]))
            rating, summary = _extract_rating(risk["aggressive_history"])
            ratings.append(("Aggressive Analyst", rating, summary))
        if risk.get("conservative_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "conservative.md").write_text(risk["conservative_history"], encoding="utf-8")
            risk_parts.append(("Conservative Analyst", risk["conservative_history"]))
            rating, summary = _extract_rating(risk["conservative_history"])
            ratings.append(("Conservative Analyst", rating, summary))
        if risk.get("neutral_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "neutral.md").write_text(risk["neutral_history"], encoding="utf-8")
            risk_parts.append(("Neutral Analyst", risk["neutral_history"]))
            rating, summary = _extract_rating(risk["neutral_history"])
            ratings.append(("Neutral Analyst", rating, summary))
        if risk_parts:
            content = "\n\n".join(f"### {name}\n{text}" for name, text in risk_parts)
            sections.append(f"## IV. Risk Management Team Decision\n\n{content}")

        # 5. Portfolio Manager
        if risk.get("judge_decision"):
            portfolio_dir = save_path / "5_portfolio"
            portfolio_dir.mkdir(exist_ok=True)
            (portfolio_dir / "decision.md").write_text(risk["judge_decision"], encoding="utf-8")
            sections.append(f"## V. Portfolio Manager Decision\n\n### Portfolio Manager\n{risk['judge_decision']}")
            rating, summary = _extract_rating(risk["judge_decision"])
            ratings.append(("Portfolio Manager", rating, summary))

    # Build executive summary and prepend to sections
    summary_section = _build_executive_summary(ratings)
    if summary_section:
        sections.insert(0, summary_section)

    # Write consolidated report
    header = f"# Trading Analysis Report: {ticker}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    (save_path / "complete_report.md").write_text(header + "\n\n".join(sections), encoding="utf-8")
    return save_path / "complete_report.md"


def _build_executive_summary(ratings: list[tuple[str, str, str]]) -> str:
    """Build executive summary section with final rating and analyst summaries.

    Args:
        ratings: List of (role, rating, summary) tuples

    Returns:
        Formatted markdown section, or empty string if no ratings.
    """
    if not ratings:
        return ""

    # Find Portfolio Manager's final rating (should be the last entry)
    final_rating = "N/A"
    for role, rating, _ in reversed(ratings):
        if role == "Portfolio Manager":
            final_rating = rating
            break

    # Build the summary table
    lines = [
        "## Executive Summary",
        "",
        f"**Final Rating: {final_rating}**",
        "",
        "| Role | Rating | Key Point |",
        "|------|--------|-----------|",
    ]

    for role, rating, summary in ratings:
        # Escape pipe characters in summary for table formatting
        safe_summary = summary.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {role} | {rating} | {safe_summary} |")

    return "\n".join(lines)

