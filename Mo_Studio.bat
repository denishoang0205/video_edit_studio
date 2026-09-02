@echo off
title TikTok Studio Pro Launcher
cd /d "%~dp0"

set "PY_EXE=pythonw.exe"
if exist "%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Launcher\pyw.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Launcher\pyw.exe"
)

curl -s -m 1 http://127.0.0.1:8000/api/settings >nul 2>&1
if %errorlevel% equ 0 goto OPEN_BROWSER

start "" "%PY_EXE%" server.py
ping 127.0.0.1 -n 3 >nul

:OPEN_BROWSER
start http://localhost:8000
exit