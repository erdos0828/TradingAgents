#!/usr/bin/env python3
"""Migrate existing report directories to the {ticker}/{date}_{time} layout.

Layouts that will be migrated:
    reports/{ticker}_{YYYYMMDD}_{HHMMSS}/
    reports/stockcode/{ticker}/{YYYY-MM-DD}/
    reports/{ticker}/{YYYY-MM-DD}/

Target layout:
    reports/{ticker}/{YYYY-MM-DD}_{HHMMSS}/
        1_analysts/
        2_research/
        ...

Run with --dry-run first to preview what will be moved.
"""

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

OLD_DIR_PATTERN = re.compile(r"^(?P<ticker>.+)_(?P<date>\d{8})_(?P<time>\d{6})$")


def parse_old_dir_name(name: str) -> tuple[str, str] | None:
    """Parse 'TICKER_YYYYMMDD_HHMMSS' and return (ticker, YYYY-MM-DD)."""
    match = OLD_DIR_PATTERN.match(name)
    if not match:
        return None
    ticker = match.group("ticker")
    raw_date = match.group("date")
    try:
        parsed = datetime.strptime(raw_date, "%Y%m%d")
    except ValueError:
        return None
    return ticker, parsed.strftime("%Y-%m-%d")


def _resolve_source_path(reports_dir: Path, verbose: bool) -> list[tuple[Path, str, str]]:
    """Find all report directories that need migration.

    Returns a list of (source_path, ticker, date_time_str) tuples.
    """
    sources: list[tuple[Path, str, str]] = []

    # 1. Old flat layout: reports/{ticker}_{YYYYMMDD}_{HHMMSS}/
    for old_path in sorted(reports_dir.iterdir()):
        if not old_path.is_dir():
            continue
        parsed = parse_old_dir_name(old_path.name)
        if parsed is not None:
            ticker, date_str = parsed
            # Use the original timestamp from the directory name.
            sources.append((old_path, ticker, f"{date_str}_{OLD_DIR_PATTERN.match(old_path.name).group('time')}"))
            continue
        if verbose:
            print(f"Skipping (does not match old pattern): {old_path.name}")

    # 2. Previously migrated layouts
    # 2a. reports/stockcode/{ticker}/{date}/
    stockcode_dir = reports_dir / "stockcode"
    if stockcode_dir.exists():
        for ticker_dir in sorted(stockcode_dir.iterdir()):
            if not ticker_dir.is_dir():
                continue
            for date_dir in sorted(ticker_dir.iterdir()):
                if not date_dir.is_dir():
                    continue
                sources.append((date_dir, ticker_dir.name, f"{date_dir.name}_000000"))

    # 2b. reports/{ticker}/{date}/ (no timestamp)
    for ticker_dir in sorted(reports_dir.iterdir()):
        if not ticker_dir.is_dir() or ticker_dir.name == "stockcode":
            continue
        for date_dir in sorted(ticker_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            try:
                datetime.strptime(date_dir.name, "%Y-%m-%d")
                sources.append((date_dir, ticker_dir.name, f"{date_dir.name}_000000"))
            except ValueError:
                pass

    return sources


def migrate(
    reports_dir: Path,
    *,
    dry_run: bool = False,
    overwrite: bool = False,
    verbose: bool = False,
) -> int:
    """Migrate report directories under ``reports_dir`` to the {ticker}/{date}_{time} layout.

    Returns the number of directories migrated.
    """
    if not reports_dir.exists():
        print(f"Source directory does not exist: {reports_dir}", file=sys.stderr)
        return 0

    migrated = 0
    sources = _resolve_source_path(reports_dir, verbose)

    for source_path, ticker, date_time_str in sources:
        new_path = reports_dir / ticker / date_time_str

        if new_path.exists() and any(new_path.iterdir()) and not overwrite:
            print(
                f"Skipping (target already exists): {source_path} -> {new_path}",
                file=sys.stderr,
            )
            continue

        print(f"{'[DRY-RUN] ' if dry_run else ''}{source_path} -> {new_path}")
        if dry_run:
            migrated += 1
            continue

        new_path.parent.mkdir(parents=True, exist_ok=True)
        if new_path.exists():
            # Remove empty or partially existing target if overwrite is allowed.
            shutil.rmtree(new_path)
        shutil.move(str(source_path), str(new_path))
        migrated += 1

    # Clean up empty directories left behind by the migration.
    if not dry_run:
        _remove_empty_dirs(reports_dir / "stockcode")

    return migrated


def _remove_empty_dirs(root: Path) -> None:
    """Remove empty directories bottom-up, starting from ``root``."""
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    if root.exists() and not any(root.iterdir()):
        root.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate report directories to reports/{ticker}/{date}_{time}/."
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path.cwd() / "reports",
        help="Directory containing old-style report folders (default: ./reports).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be moved without moving anything.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite target directories if they already exist.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print skipped entries too.",
    )
    args = parser.parse_args()

    count = migrate(
        args.reports_dir,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        verbose=args.verbose,
    )
    print(f"\nMigrated {count} director{'y' if count == 1 else 'ies'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
