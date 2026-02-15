' SillyTavern Campaign Manager - Silent Background Launcher
' Double-click this to run STCM without a visible console window.
' To stop it, use Task Manager or the Windows "Stop-STCM.bat" script.

Set objShell = CreateObject("WScript.Shell")
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' Run Start-STCM.bat hidden (window style 0 = hidden)
objShell.Run "cmd /c """ & strPath & "\Start-STCM.bat""", 0, False
