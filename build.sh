#!/usr/bin/env bash
# Build etoken app for macOS using PyInstaller
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== etoken build (macOS) ==="

echo "[1/4] Installing dependencies..."
pip install -r requirements.txt
pip install pyinstaller

echo "[2/4] Installing Playwright Chromium..."
python -m playwright install chromium

echo "[3/4] Running PyInstaller..."
pyinstaller etoken.spec --clean --noconfirm

echo "[4/4] Creating zip archive..."
cd dist
ZIP_NAME="etoken-mac-$(date +%Y%m%d-%H%M%S).zip"
zip -r "$ZIP_NAME" etoken/
echo "Archive created: dist/$ZIP_NAME"

echo ""
echo "=== Build complete ==="
echo "Output: dist/etoken/"
echo "Archive: dist/$ZIP_NAME"
echo ""
echo "To test: ./dist/etoken/etoken"
