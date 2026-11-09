@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    py -3 main.py
)
if errorlevel 1 (
    echo.
    echo Could not start Gomoku. See README.md for Python and Pygame setup.
    pause
)
