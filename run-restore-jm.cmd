@echo off
cd /d D:\project\cs-rpa
echo Restore dongdong live inbox tab 0 after a person clicked the UI. never click send.
.venv\Scripts\python.exe -m ui.web_jingmai restore %*
