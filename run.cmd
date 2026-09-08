@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m mock_dongdong %*
) else (
    python -m mock_dongdong %*
)
exit /b %errorlevel%
