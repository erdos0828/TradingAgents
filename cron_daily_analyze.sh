#!/bin/bash
set -e
cd /workspace/TradingAgents
source .venv/bin/activate
tradingagents analyze-portfolio
git add reports/
if ! git diff --cached --quiet; then
    git commit -m "daily reports $(date +%Y-%m-%d)"
fi
git push origin main
