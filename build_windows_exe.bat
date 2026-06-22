@echo off
setlocal

call conda activate isyntax_py37

set PYTHONNOUSERSITE=1

python -m pip install --upgrade "pip<24"
pip install -r requirements-windows-py37.txt

pyinstaller --clean --noconfirm iSyntaxToTIFF.spec

echo.
echo Build finished.
echo Output:
echo dist\iSyntaxToTIFF\iSyntaxToTIFF.exe
echo.
pause