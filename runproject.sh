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
BUILD_SCRIPT="$SCRIPT_DIR_WIN\\build_exe.py"
APP_EXE="$SCRIPT_DIR/release/OwlcatPortraitTool/OwlcatPortraitTool.exe"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "Could not find the virtual environment Python at:"
    echo "  $VENV_PYTHON"
    echo
    echo "Run this first:"
    echo "  source ./setenv.sh"
    exit 1
fi

# Always run the build to ensure the latest changes are included. The build
# script handles cleaning up old artifacts.
"$VENV_PYTHON" -u "$BUILD_SCRIPT"
BUILD_STATUS=$?
if [ "$BUILD_STATUS" -ne 0 ]; then
    exit "$BUILD_STATUS"
fi

if [ ! -x "$APP_EXE" ]; then
    echo "Build completed, but the executable was not found at:"
    echo "  $APP_EXE"
    exit 1
fi

exec "$APP_EXE" "$@"
