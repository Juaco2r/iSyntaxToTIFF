#!/usr/bin/env bash
set -euo pipefail

python3.8 -m venv .venv-isyntax-linux
source .venv-isyntax-linux/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements-linux-py38.txt

rm -rf dist build

python -m PyInstaller --version
python -m PyInstaller --clean --noconfirm --distpath "$PWD/dist" --workpath "$PWD/build" "$PWD/iSyntaxToTIFF.spec"

echo "Listing generated files:"
find dist -maxdepth 5 -print

if [ ! -f "dist/iSyntaxToTIFF/iSyntaxToTIFF" ]; then
    echo "Expected output was not found: dist/iSyntaxToTIFF/iSyntaxToTIFF"
    exit 1
fi

echo
echo "Build finished."
echo "Output:"
echo "dist/iSyntaxToTIFF/iSyntaxToTIFF"
echo
