@echo off
title TikTok Studio Pro Launcher
cd /d "%~dp0"

:: 1. Kiem tra xem server da chay chua
curl -s -m 1 http://localhost:8000/api/settings >nul 2>&1
if %errorlevel% neq 0 (
    start "" pythonw.exe "%~dp0server.py"
    timeout /t 1 /nobreak >nul
)

:: 2. Mo Webapp tren trinh duyet mac dinh
start http://localhost:8000
exit
