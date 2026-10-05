#!/bin/sh
# Kept for older install prompts. The installer is setup/install.py, which also runs on Windows.
DIR=$(dirname "$0")
PY=$(command -v python3 || command -v python) || { echo "error: GroundWork needs Python 3.10 or newer." >&2; exit 1; }
exec "$PY" "$DIR/install.py" "$@"
