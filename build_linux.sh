#!/usr/bin/env bash
set -e

python3.8 -m venv .venv-isyntax-linux
source .venv-isyntax-linux/bin/activate

python -m pip install --upgrade pip
pip install -r requirements-linux-py38.txt

pyinstaller --clean --noconfirm iSyntaxToTIFF.spec

echo
echo "Build finished."
echo "Output:"
echo "dist/iSyntaxToTIFF/iSyntaxToTIFF"
echo