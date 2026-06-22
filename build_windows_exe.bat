@echo off
REM Build iSyntaxToTIFF Windows EXE WITHOUT bundling Philips SDK.
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
python -m pip install -r requirements.txt

pyinstaller --clean --noconfirm iSyntaxToTIFF.spec

if exist "dist\iSyntaxToTIFF\iSyntaxToTIFF.exe" (
    echo.
    echo Build OK:
    echo dist\iSyntaxToTIFF\iSyntaxToTIFF.exe
    echo.
    echo You can zip and distribute the full folder:
    echo dist\iSyntaxToTIFF
) else (
    echo Build failed: EXE not found.
    pause
    exit /b 1
)

pause
