Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
rootDir = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
strDesktop = WshShell.SpecialFolders("Desktop")
Set oShortcut = WshShell.CreateShortcut(strDesktop & "\TikTok Studio Pro.lnk")
oShortcut.TargetPath = rootDir & "\Open_Studio.vbs"
oShortcut.WorkingDirectory = rootDir
oShortcut.Description = "Mở TikTok Video Studio Pro (Chạy ngầm không hiện cửa sổ)"
If fso.FileExists(rootDir & "\ui\favicon.png") Then
    oShortcut.IconLocation = rootDir & "\ui\favicon.png, 0"
Else
    oShortcut.IconLocation = "shell32.dll, 14"
End If
oShortcut.Save

