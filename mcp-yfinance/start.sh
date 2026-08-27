#!/usr/bin/env bash
# Quick start script for the yfinance MCP server.
# Usage: ./start.sh [PORT]

set -euo pipefail

PORT="${1:-8080}"
HOST="${HOST:-0.0.0.0}"

# Prefer a local venv if it exists
if [[ -d .venv ]]; then
    PYTHON=.venv/bin/python
else
    PYTHON=python3
fi

exec "${PYTHON}" -m mcp_yfinance.server --host "${HOST}" --port "${PORT}"
