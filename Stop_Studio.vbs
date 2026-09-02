' ==============================================================================
' TikTok Video Studio Pro - Dung Server Ngam
' ==============================================================================
Option Explicit

Dim WshShell
Set WshShell = CreateObject("WScript.Shell")

' Dung tat ca tien trinh pythonw dang chay server.py ma khong hien thi bat ky cua so nao
WshShell.Run "taskkill /F /IM pythonw.exe", 0, True

WScript.Sleep 500
MsgBox "Da dung may chu TikTok Studio ngam thanh cong!", vbInformation, "TikTok Studio Pro"
