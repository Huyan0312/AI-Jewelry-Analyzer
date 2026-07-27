Set WshShell = CreateObject("WScript.Shell")
Set Fso = CreateObject("Scripting.FileSystemObject")
ScriptDir = Fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "cmd.exe /c """ & ScriptDir & "\start_watcher.bat""", 0, False
