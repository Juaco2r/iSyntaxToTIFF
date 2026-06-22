@echo off
setlocal

call conda activate isyntax_py37
if errorlevel 1 (
    echo Could not activate conda environment isyntax_py37.
    echo Create it first with: conda env create -f environment.yml
    exit /b 1
)

set PYTHONNOUSERSITE=1

python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo pip was not found in this environment. Installing pip with conda...
    conda install -n isyntax_py37 -y pip setuptools wheel
    if errorlevel 1 exit /b 1
)

python -m pip install --upgrade "pip<24" setuptools wheel
if errorlevel 1 exit /b 1

python -m pip install -r requirements-windows-py37.txt
if errorlevel 1 exit /b 1

if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

python -m PyInstaller --version
if errorlevel 1 exit /b 1

python -m PyInstaller --clean --noconfirm --distpath "%CD%\dist" --workpath "%CD%\build" "%CD%\iSyntaxToTIFF.spec"
if errorlevel 1 exit /b 1

echo Listing generated files:
dir /s /b dist

if not exist "dist" (
    echo The dist folder was not created.
    exit /b 1
)

if not exist "dist\iSyntaxToTIFF\iSyntaxToTIFF.exe" (
    echo Expected output was not found: dist\iSyntaxToTIFF\iSyntaxToTIFF.exe
    exit /b 1
)

echo.
echo Build finished.
echo Output:
echo dist\iSyntaxToTIFF\iSyntaxToTIFF.exe
echo.
pause
