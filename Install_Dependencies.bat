@echo off
chcp 65001 >nul
title Cai Dat Moi Truong - TikTok Video Studio Pro
echo ========================================================
echo   🎬 TIKTOK VIDEO STUDIO PRO - SETUP ENVIRONMENT
echo ========================================================
echo.

echo [1/3] Kiem tra va cap nhat Pip...
python -m pip install --upgrade pip --quiet

echo [2/3] Dang cai dat cac thu vien Python tu requirements.txt...
python -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Loi khi cai dat thu vien Python. Vui long kiem tra lai Python da cai dat dung cach chua.
    pause
    exit /b 1
)

echo [3/3] Kiem tra cong cu FFmpeg...
if not exist "bin\ffmpeg.exe" (
    echo [CANH BAO] Khong tim thay bin\ffmpeg.exe!
    echo Dang tu dong tai xuong FFmpeg cho Windows...
    if not exist "bin" mkdir bin
    powershell -Command "Write-Host 'Dang tai FFmpeg...'; Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' -OutFile 'bin\ffmpeg.zip'; Expand-Archive -Path 'bin\ffmpeg.zip' -DestinationPath 'bin\temp' -Force; Move-Item -Path 'bin\temp\*\bin\ffmpeg.exe' -Destination 'bin\ffmpeg.exe' -Force; Remove-Item -Path 'bin\temp', 'bin\ffmpeg.zip' -Recurse -Force; Write-Host 'FFmpeg da duoc tai va giai nen thanh cong!'"
) else (
    echo   -> FFmpeg da co san trong thu muc bin.
)

echo.
echo ========================================================
echo   ✅ HOAN TAT CAI DAT! MOI THU DA SAN SANG.
echo   Ban chi can nhap dup vao file "Run_Studio.bat" de chay.
echo ========================================================
echo.
pause
