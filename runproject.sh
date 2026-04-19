#!/usr/bin/env bash

# Run from the project root no matter where the script is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if command -v cygpath >/dev/null 2>&1; then
    SCRIPT_DIR_WIN="$(cygpath -w "$SCRIPT_DIR")"
else
    SCRIPT_DIR_WIN="$SCRIPT_DIR"
fi

VENV_PYTHON="$SCRIPT_DIR/OwlcatPortraitToolVenv/Scripts/python.exe"
APP_SCRIPT="$SCRIPT_DIR_WIN\\UIQtRender.py"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "Could not find the virtual environment Python at:"
    echo "  $VENV_PYTHON"
    echo
    echo "Run this first:"
    echo "  source ./setenv.sh"
    exit 1
fi

exec "$VENV_PYTHON" -u "$APP_SCRIPT" "$@"
