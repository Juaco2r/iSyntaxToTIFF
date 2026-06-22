@echo off
REM Developer run from source. End users should use the EXE.
call conda activate isyntax_py37
set PYTHONNOUSERSITE=1
python src\isyntax_to_tiff\app.py
pause
