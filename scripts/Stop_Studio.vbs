Set WshShell = CreateObject("WScript.Shell")

' Dung tat ca tien trinh server dang chay ngam tren cong 8000
WshShell.Run "cmd /c taskkill /f /im pythonw.exe >nul 2>&1", 0, True
WshShell.Run "powershell -Command ""Get-Process python* -ErrorAction SilentlyContinue | Where-Object { (Get-NetTCPConnection -LocalPort 8000 -OwningProcess $_.Id -ErrorAction SilentlyContinue) } | Stop-Process -Force""", 0, True

' Hien thi thong bao nho xac nhan da dung
WshShell.Popup "Đã dừng toàn bộ dịch vụ ngầm của TikTok Studio Pro!", 3, "TikTok Studio Pro", 64
