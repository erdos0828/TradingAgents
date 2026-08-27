#!/usr/bin/env python3
"""Batch analysis script for portfolio holdings.

Reads portfolio holdings from data/portfolio_holdings.json and runs
the trading analysis for each ticker using the CLI.

Usage:
    python scripts/analyze_portfolio.py
    python scripts/analyze_portfolio.py --date 2026-08-19
    python scripts/analyze_portfolio.py --skip TSLA,AAPL
    python scripts/analyze_portfolio.py --dry-run
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Batch analyze all stocks in portfolio holdings"
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Analysis date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--analysts",
        default="market,news,fundamentals",
        help="Comma-separated analysts (default: market,news,fundamentals)",
    )
    parser.add_argument(
        "--no-dingtalk",
        action="store_true",
        help="Disable DingTalk notification (enabled by default)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show commands without executing",
    )
    parser.add_argument(
        "--holdings",
        default="data/portfolio_holdings.json",
        help="Path to holdings JSON file (default: data/portfolio_holdings.json)",
    )
    parser.add_argument(
        "--skip",
        default="",
        help="Comma-separated list of tickers to skip",
    )

    args = parser.parse_args()

    # Load holdings
    holdings_path = Path(args.holdings)
    if not holdings_path.exists():
        print(f"Error: Holdings file not found: {holdings_path}")
        sys.exit(1)

    with open(holdings_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    holdings = data.get("holdings", [])
    if not holdings:
        print("Error: No holdings found in file")
        sys.exit(1)

    # Parse skip list
    skip_tickers = {t.strip().upper() for t in args.skip.split(",") if t.strip()}

    # Filter holdings
    tickers_to_analyze = [
        h for h in holdings
        if h["ticker"].upper() not in skip_tickers
    ]

    print(f"=" * 60)
    print(f"Portfolio Batch Analysis")
    print(f"=" * 60)
    print(f"Date: {args.date}")
    print(f"Analysts: {args.analysts}")
    print(f"DingTalk: {'enabled' if not args.no_dingtalk else 'disabled'}")
    print(f"Holdings file: {holdings_path}")
    print(f"Total tickers: {len(tickers_to_analyze)}")
    if skip_tickers:
        print(f"Skipped: {', '.join(skip_tickers)}")
    print(f"=" * 60)
    print()

    # Show holdings summary
    print("Holdings to analyze:")
    for h in tickers_to_analyze:
        qty = h.get("quantity", "N/A")
        cost = h.get("cost_price", "N/A")
        print(f"  - {h['ticker']}: {qty} shares @ ${cost}")
    print()

    if args.dry_run:
        print("[DRY RUN] Commands that would be executed:")
        print()

    # Run analysis for each ticker
    success_count = 0
    fail_count = 0

    for i, holding in enumerate(tickers_to_analyze, 1):
        ticker = holding["ticker"]
        qty = holding.get("quantity", "N/A")
        cost = holding.get("cost_price", "N/A")

        print(f"[{i}/{len(tickers_to_analyze)}] Analyzing {ticker} (qty={qty}, cost=${cost})...")

        # Build command
        cmd = [
            sys.executable, "-m", "cli.main", "analyze",
            "--ticker", ticker,
            "--date", args.date,
            "--analysts", args.analysts,
            "--auto-save",
            "--headless",
        ]

        if not args.no_dingtalk:
            cmd.append("--dingtalk")

        if args.dry_run:
            print(f"  Command: {' '.join(cmd)}")
            print()
            continue

        # Execute command
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes timeout per analysis
            )

            if result.returncode == 0:
                print(f"  ✓ Success")
                # Show key output lines
                for line in result.stdout.split("\n"):
                    if "auto-saved" in line.lower() or "dingtalk" in line.lower():
                        print(f"    {line.strip()}")
                success_count += 1
            else:
                print(f"  \u2717 Failed (exit code: {result.returncode})")
                if result.stderr:
                    # Print full stderr for debugging (was truncated to 200 chars)
                    for line in result.stderr.strip().split("\n"):
                        print(f"    {line}")
                fail_count += 1

        except subprocess.TimeoutExpired:
            print(f"  ✗ Timeout (>10 minutes)")
            fail_count += 1
        except Exception as e:
            print(f"  ✗ Exception: {e}")
            fail_count += 1

        print()

    # Summary
    print("=" * 60)
    print("Batch Analysis Complete")
    print("=" * 60)
    if args.dry_run:
        print(f"[DRY RUN] Would analyze {len(tickers_to_analyze)} tickers")
    else:
        print(f"Success: {success_count}")
        print(f"Failed: {fail_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
