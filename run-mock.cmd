@echo off
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
echo Open http://127.0.0.1:18766/workbench in Codex.
.venv\Scripts\python.exe -m mock_dongdong serve %*
