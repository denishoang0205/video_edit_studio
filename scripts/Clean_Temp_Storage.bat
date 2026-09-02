@echo off
chcp 65001 >nul
title Dọn dẹp bộ nhớ tạm - TikTok Studio Pro
color 0E
cd /d "%~dp0\.."

echo ========================================================================
echo        🧹 DỌN DẸP BỘ NHỚ TẠM (STORAGE CLEANER)
echo ========================================================================
echo.
echo Đang quét và dọn dẹp các tệp tạm thời trong storage\temp và scratch...

python -c "
import os, shutil
base = os.path.dirname(os.path.abspath('.'))
temp_dirs = [os.path.join('.', 'storage', 'temp'), os.path.join('.', 'scratch')]
count = 0
for td in temp_dirs:
    if os.path.exists(td):
        for item in os.listdir(td):
            p = os.path.join(td, item)
            try:
                if os.path.isfile(p) or os.path.islink(p):
                    os.unlink(p)
                    count += 1
                elif os.path.isdir(p):
                    shutil.rmtree(p)
                    count += 1
            except Exception as e:
                pass
print(f'Da don dep {count} tep tam.')
"

echo.
echo ✅ Đã dọn dẹp thành công!
timeout /t 3 >nul
