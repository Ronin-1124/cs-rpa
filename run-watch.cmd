@echo off
cd /d D:\project\cs-rpa
echo Watching Qianniu / Jingmai notify popups. auto_send=false
.venv\Scripts\python.exe main.py %*
