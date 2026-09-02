Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Lay thu muc goc
scriptDir = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
WshShell.CurrentDirectory = scriptDir

' 1. Chay Python Server ngam 100% khong cua so console (0 = An cua so)
WshShell.Run "pythonw.exe server.py", 0, False

' 2. Cho 1.5 giay de Server san sang
WScript.Sleep 1500

' 3. Tu dong mo Webapp Studio truc tiep tren trinh duyet
WshShell.Run "http://localhost:8000", 1, False
