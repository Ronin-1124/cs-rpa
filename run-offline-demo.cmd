@echo off
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
.venv\Scripts\python.exe -X utf8 offline_demo.py
pause
