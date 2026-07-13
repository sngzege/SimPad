#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/seng/snap/code/249/.local/bin/python3.12}"

"$PYTHON_BIN" -m pip install --user --break-system-packages pyinstaller

rm -rf build dist dist-win

"$PYTHON_BIN" -m PyInstaller --onefile --noconsole --add-data "config.json:." --name simpad-linux simpad.py
chmod +x dist/simpad-linux

echo "Linux build: dist/simpad-linux"
