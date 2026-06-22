#!/usr/bin/env bash
set -e

python3.8 -m venv .venv-isyntax-linux
source .venv-isyntax-linux/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements-linux-py38.txt

rm -rf dist build
python -m PyInstaller --clean --noconfirm --distpath "$(pwd)/dist" --workpath "$(pwd)/build" "$(pwd)/iSyntaxToTIFF.spec"

test -d "dist/iSyntaxToTIFF"

echo
echo "Build finished."
echo "Output:"
echo "dist/iSyntaxToTIFF/iSyntaxToTIFF"
echo
