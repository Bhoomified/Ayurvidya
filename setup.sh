#!/usr/bin/env bash
# One-time setup on macOS/Linux. Run from the project folder:  bash setup.sh
set -e
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-core.txt
.venv/bin/python -m unittest discover -s tests
echo "Setup OK. Activate with:  source .venv/bin/activate"
