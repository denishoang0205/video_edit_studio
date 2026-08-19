@echo off
chcp 65001 >nul
title TikTok Video Studio Pro (Automation Webform)
cd /d "%~dp0"

echo ========================================================
echo    🎬 TIKTOK VIDEO STUDIO PRO - AUTOMATION PIPELINE
echo ========================================================
echo [1/2] Dang khoi dong Webform Studio Server...
echo [2/2] Dang mo trinh duyet tai: http://localhost:8000
echo.

:: Mo trinh duyet sau 1 giay
start "" http://localhost:8000

:: Chay backend server
python server.py

pause
