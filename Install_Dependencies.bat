@echo off
chcp 65001 >nul
title TikTok Studio Pro - Cài Đặt Môi Trường & Thư Viện
color 0b
cd /d "%~dp0"

echo ========================================================================
echo          🎬 TIKTOK STUDIO PRO - CÀI ĐẶT MÔI TRƯỜNG & PHỤ THUỘC
echo ========================================================================
echo.

:: 1. Kiểm tra Python
echo [1/5] Kiểm tra môi trường Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LỖI] Không tìm thấy Python trên máy tính!
    echo Vui lòng tải và cài đặt Python 3.8+ từ https://www.python.org/downloads/
    echo Lưu ý quan trọng: Nhớ tích chọn ô "Add python.exe to PATH" khi cài đặt!
    echo.
    pause
    exit /b 1
)
python --version
echo [OK] Đã tìm thấy Python.
echo.

:: 2. Cài đặt các thư viện từ requirements.txt
echo [2/5] Đang nâng cấp pip và cài đặt các thư viện cần thiết...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [CẢNH BÁO] Có một số gói cài đặt bị lỗi, đang thử cài đặt từng gói...
    python -m pip install Pillow yt-dlp requests edge-tts deep-translator
)
echo [OK] Hoàn tất cài đặt thư viện.
echo.

:: 3. Tạo cấu trúc thư mục chuẩn
echo [3/5] Khởi tạo các thư mục lưu trữ dữ liệu...
if not exist "data" mkdir "data"
if not exist "input_sources" mkdir "input_sources"
if not exist "output_product" mkdir "output_product"
if not exist "bin" mkdir "bin"
if not exist "assets\fonts" mkdir "assets\fonts"
if not exist "assets\presets" mkdir "assets\presets"

:: Sao chép cấu hình mẫu nếu chưa có
if not exist "data\accounts.json" (
    if exist "data\accounts.example.json" (
        copy "data\accounts.example.json" "data\accounts.json" >nul
        echo [OK] Đã khởi tạo data\accounts.json từ mẫu.
    )
)

if not exist "data\settings.json" (
    if exist "data\settings.example.json" (
        copy "data\settings.example.json" "data\settings.json" >nul
        echo [OK] Đã khởi tạo data\settings.json từ mẫu.
    )
)
echo [OK] Cấu trúc thư mục sẵn sàng.
echo.

:: 4. Tạo Shortcut 1-Click
echo [4/5] Đang tạo Shortcut 1-Click trên Desktop và thư mục gốc...
powershell -NoProfile -Command "$wsh = New-Object -ComObject WScript.Shell; $root = (Get-Location).Path; $vbs = Join-Path $root 'Open_Studio.vbs'; $ico = Join-Path $root 'ui\favicon.png'; $s1 = $wsh.CreateShortcut((Join-Path $root 'TikTok Studio Pro.lnk')); $s1.TargetPath = $vbs; $s1.WorkingDirectory = $root; $s1.IconLocation = $ico + ',0'; $s1.Save(); $desk = [System.Environment]::GetFolderPath('Desktop'); $s2 = $wsh.CreateShortcut((Join-Path $desk 'TikTok Studio Pro.lnk')); $s2.TargetPath = $vbs; $s2.WorkingDirectory = $root; $s2.IconLocation = $ico + ',0'; $s2.Save();"
echo [OK] Đã tạo Shortcut "TikTok Studio Pro".
echo.

:: 5. Kiểm tra FFmpeg
echo [5/5] Kiểm tra công cụ biên tập FFmpeg...
if exist "bin\ffmpeg.exe" (
    echo [OK] Đã tìm thấy bin\ffmpeg.exe.
) else (
    ffmpeg -version >nul 2>&1
    if %errorlevel% equ 0 (
        echo [OK] Đã tìm thấy FFmpeg toàn cục trong PATH hệ thống.
    ) else (
        echo [CHÚ Ý] Chưa tìm thấy FFmpeg trong bin\ffmpeg.exe.
        echo Hệ thống sẽ tự động dùng FFmpeg khi bạn đặt file vào thư mục bin\.
    )
)

echo.
echo ========================================================================
echo              🎉 CÀI ĐẶT HOÀN TẤT THÀNH CÔNG 100%!
echo ========================================================================
echo.
echo 👉 Cách sử dụng:
echo - Nhấp đúp vào icon "TikTok Studio Pro" trên Desktop hoặc trong thư mục này.
echo - Hoặc nhấp đúp file "Open_Studio.bat" / "Open_Studio.vbs".
echo - Trình duyệt sẽ tự động mở http://localhost:8000 để làm việc.
echo.
pause