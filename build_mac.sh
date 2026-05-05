#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "Cleaning previous build artifacts..."
rm -rf build dist

echo "Building macOS app with PyInstaller..."
if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Error: Python is not installed or not available in PATH."
  exit 1
fi

$PYTHON -m PyInstaller Mac.spec

echo "Build complete. Check dist/ for the generated app."
