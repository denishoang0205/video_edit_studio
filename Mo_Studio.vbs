Option Explicit

Dim WshShell, fso, scriptDir, http, url, checkUrl, isRunning, i, serverPy, pyExe, cmd, localApp

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir
serverPy = scriptDir & "\server.py"
url = "http://localhost:8000"
checkUrl = "http://127.0.0.1:8000/api/settings"
localApp = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")

' 1. Xac dinh duong dan Python chinh xac
pyExe = "pythonw.exe"
If fso.FileExists(localApp & "\Programs\Python\Python314\pythonw.exe") Then
    pyExe = localApp & "\Programs\Python\Python314\pythonw.exe"
ElseIf fso.FileExists(localApp & "\Programs\Python\Launcher\pyw.exe") Then
    pyExe = localApp & "\Programs\Python\Launcher\pyw.exe"
End If

' 2. Kiem tra xem Server da hoat dong chua (dung truc tiep 127.0.0.1 chong loi IPv6)
isRunning = False
On Error Resume Next
Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
http.setTimeouts 800, 800, 800, 800
http.Open "GET", checkUrl, False
http.Send
If Err.Number = 0 And http.Status = 200 Then
    isRunning = True
End If
On Error GoTo 0

' 3. Neu Server chua chay thi khoi dong ngam bang pythonw
If Not isRunning Then
    cmd = """" & pyExe & """ """ & serverPy & """"
    WshShell.Run cmd, 0, False
    
    ' Cho server san sang (toi da 3 giay)
    For i = 1 To 15
        WScript.Sleep 200
        On Error Resume Next
        Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
        http.setTimeouts 300, 300, 300, 300
        http.Open "GET", checkUrl, False
        http.Send
        If Err.Number = 0 And http.Status = 200 Then
            Exit For
        End If
        On Error GoTo 0
    Next
End If

' 4. Tu dong mo Webapp tren trinh duyet mac dinh
WshShell.Run url, 1, False