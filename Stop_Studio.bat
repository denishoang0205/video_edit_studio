@echo off
chcp 65001 >nul
title TikTok Studio Pro - Dừng Máy Chủ
color 0c
cd /d "%~dp0"

echo Đang dừng toàn bộ máy chủ và tiến trình TikTok Studio...
taskkill /F /IM pythonw.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq TikTok Studio*" >nul 2>&1

echo [OK] Đã dừng toàn bộ dịch vụ ngầm thành công.
timeout /t 2 >nul
exit