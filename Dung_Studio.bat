@echo off
title TikTok Studio Pro - Stop Server
cd /d "%~dp0"
taskkill /F /IM pythonw.exe /T >nul 2>&1
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
echo ======================================================
echo    DA DUNG MAY CHU TIKTOK STUDIO PRO THANH CONG!
echo ======================================================
timeout /t 2 /nobreak >nul
exit
