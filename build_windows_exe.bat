@echo off
REM Build iSyntaxToTIFF Windows app.
REM Run from Anaconda Prompt or normal CMD if conda is available.

call conda activate isyntax_py37
if errorlevel 1 (
    echo Could not activate conda environment isyntax_py37.
    echo Create it first with: conda env create -f environment.yml
    pause
    exit /b 1
)

set PYTHONNOUSERSITE=1

python -m pip install --upgrade "pip<24"
python -m pip install -r requirements-windows-py37.txt

pyinstaller --clean --noconfirm iSyntaxToTIFF.spec

if exist "dist\iSyntaxToTIFF\iSyntaxToTIFF.exe" (
    echo.
    echo Build OK:
    echo dist\iSyntaxToTIFF\iSyntaxToTIFF.exe
    echo.
    echo Zip and distribute the full folder:
    echo dist\iSyntaxToTIFF
) else (
    echo.
    echo The exact expected EXE path was not found. Listing dist folder for debugging:
    dir /s /b dist
    echo.
    echo If an iSyntaxToTIFF executable appears elsewhere inside dist, the GitHub workflow will package it automatically.
    pause
    exit /b 1
)

pause
