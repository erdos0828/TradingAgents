#!/bin/bash
set -e
cd /workspace/TradingAgents
source .venv/bin/activate

# Optional market filter: a-share | us | all (default)
MARKET="${1:-all}"
tradingagents analyze-portfolio --market "$MARKET"

git add reports/
if ! git diff --cached --quiet; then
    git commit -m "daily reports $(date +%Y-%m-%d) ${MARKET}"
fi
git push origin main
