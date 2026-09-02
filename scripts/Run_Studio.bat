@echo off
chcp 65001 >nul
title TikTok Video Studio Pro - All-in-One Automation Hub
color 0B
cd /d "%~dp0"

echo ========================================================================
echo        🎬 TIKTOK VIDEO STUDIO PRO - ALL-IN-ONE AUTOMATION HUB
echo ========================================================================
echo.
echo [1/3] Đang khởi động Backend Web Server (Cổng 8000)...
start "TikTok Studio Backend" /min cmd /c "python server.py"

echo [2/3] Đang khởi động n8n Workflow Engine (Cổng 5678)...
where npx >nul 2>&1
if %errorlevel% equ 0 (
    start "n8n Engine" /min cmd /c "npx n8n"
) else (
    echo       (Lưu ý: Chưa tìm thấy npx/NodeJS, n8n engine sẽ được khởi chạy khi cài đặt)
)

echo [3/3] Đang mở Webapp Dashboard tại: http://localhost:8000
timeout /t 2 /nobreak >nul
start "" http://localhost:8000

echo.
echo ========================================================================
echo  ✅ HỆ THỐNG ĐÃ KHỞI CHẠY THÀNH CÔNG!
echo.
echo  🌐 Webapp Studio: http://localhost:8000
echo  🤖 n8n Dashboard: http://localhost:5678
echo.
echo  👉 Bạn chỉ việc vào giao diện Webapp và bấm "KÍCH HOẠT PIPELINE"!
echo ========================================================================
echo.
echo (Cửa sổ này đang duy trì các tiến trình nền. Nhấn phím bất kỳ để dừng toàn bộ)
pause >nul
taskkill /f /im python.exe /fi "WINDOWTITLE eq TikTok Studio Backend*" >nul 2>&1
exit
