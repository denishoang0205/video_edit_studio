@echo off
chcp 65001 >nul
title TikTok Studio Pro - Nightly Automation Hub
color 0A

echo ========================================================================
echo        🌙 TIKTOK STUDIO PRO - TỰ ĐỘNG HÓA BAN ĐÊM (LOCAL ENGINE)
echo ========================================================================
echo.
echo [1/3] Đang kiểm tra môi trường Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LỖI] Không tìm thấy Python! Vui lòng cài đặt Python và tích chọn Add to PATH.
    pause
    exit /b 1
)

echo [2/3] Khởi động TikTok Studio Server (Cổng 8000)...
start "TikTok Studio Server" /min cmd /c "python server.py"

echo [3/3] Khởi động n8n Workflow Engine (Cổng 5678)...
start "n8n Automation Engine" /min cmd /c "npx n8n"

echo.
echo ========================================================================
echo  ✅ HỆ THỐNG ĐÃ SẴN SÀNG CHẠY TỰ ĐỘNG BAN ĐÊM!
echo.
echo  🌐 TikTok Studio Web: http://localhost:8000
echo  🤖 n8n Dashboard:     http://localhost:5678
echo.
echo  💤 HƯỚNG DẪN TRƯỚC KHI ĐI NGỦ:
echo  1. Đảm bảo n8n đã được gạt nút "Active" (Bật Workflow).
echo  2. Với Máy tính bàn (PC): Bạn chỉ cần TẮT MÀN HÌNH (CPU vẫn bật).
echo  3. Với Laptop: Gập nắp máy lại (Đã chỉnh 'When I close lid: Do nothing').
echo  4. Đúng 12h đêm, hệ thống sẽ tự đăng video và báo về Telegram cho bạn!
echo ========================================================================
echo.
echo Nhấn phím bất kỳ để mở giao diện n8n...
pause >nul
start http://localhost:5678
