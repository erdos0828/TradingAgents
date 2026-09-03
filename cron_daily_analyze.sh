#!/bin/bash
set -e

# Locate project root from this script's location so the same script works
# both locally and in Aone Sandbox /workspace/TradingAgents.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

source .venv/bin/activate

# Optional market filter: a-share | us | all (default)
MARKET="${1:-all}"
tradingagents analyze-portfolio --market "$MARKET"

git add reports/
if ! git diff --cached --quiet; then
    git commit -m "daily reports $(date +%Y-%m-%d) ${MARKET}"
fi
git push alibaba main
