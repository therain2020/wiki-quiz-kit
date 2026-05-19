#!/bin/bash
# wiki-quiz-kit bootstrap — check Python, then hand off to setup.py
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

if command -v python3 &>/dev/null; then
    PY=python3
elif command -v python &>/dev/null; then
    PY=python
else
    echo "Python 3 is required. Install it and re-run:"
    echo "  macOS:   brew install python3"
    echo "  Windows: winget install python3"
    echo "  Linux:   sudo apt install python3"
    exit 1
fi

exec "$PY" "$ROOT/setup.py"
