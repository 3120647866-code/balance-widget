' API Balance Widget — silent launcher (no console window)
Set WshShell = CreateObject("WScript.Shell")

' Use pythonw.exe to avoid console window
Dim pythonwPath, scriptPath
pythonwPath = "D:\python\pythonw.exe"
scriptPath = "D:\app\balance-widget\balance_widget.py"

' Load environment from Claude settings before launching
Dim fso, settingsPath, envCmd
Set fso = CreateObject("Scripting.FileSystemObject")
settingsPath = WshShell.ExpandEnvironmentStrings("%USERPROFILE%") & "\.claude\settings.json"

envCmd = ""
If fso.FileExists(settingsPath) Then
    Dim file, content
    Set file = fso.OpenTextFile(settingsPath, 1)
    content = file.ReadAll
    file.Close

    ' Extract ANTHROPIC_AUTH_TOKEN
    envCmd = envCmd & ExtractEnv(content, "ANTHROPIC_AUTH_TOKEN")
    envCmd = envCmd & ExtractEnv(content, "ANTHROPIC_BASE_URL")
    envCmd = envCmd & ExtractEnv(content, "ANTHROPIC_DEFAULT_HAIKU_MODEL")
    envCmd = envCmd & ExtractEnv(content, "ANTHROPIC_DEFAULT_SONNET_MODEL")
    envCmd = envCmd & ExtractEnv(content, "ANTHROPIC_DEFAULT_OPUS_MODEL")
    envCmd = envCmd & ExtractEnv(content, "ANTHROPIC_DEFAULT_FABLE_MODEL")
    envCmd = envCmd & ExtractEnv(content, "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME")
    envCmd = envCmd & ExtractEnv(content, "ANTHROPIC_DEFAULT_OPUS_MODEL_NAME")
    envCmd = envCmd & ExtractEnv(content, "ANTHROPIC_DEFAULT_FABLE_MODEL_NAME")
    envCmd = envCmd & ExtractEnv(content, "ANTHROPIC_MODEL")
    envCmd = envCmd & ExtractEnv(content, "DASHSCOPE_API_KEY")
    envCmd = envCmd & ExtractEnv(content, "VISION_PROVIDER")
End If

' Run: set env vars then launch pythonw
WshShell.Run "cmd /c " & envCmd & """" & pythonwPath & """ """ & scriptPath & """", 0, False

' ── Helper: extract JSON key → SET KEY=VALUE ──
Function ExtractEnv(json, keyName)
    Dim pos, startPos, endPos, val
    pos = InStr(json, """" & keyName & """")
    If pos > 0 Then
        startPos = InStr(pos, json, ":") + 1
        ' Find the value between quotes
        startPos = InStr(startPos, json, """")
        If startPos > 0 Then
            startPos = startPos + 1
            endPos = InStr(startPos, json, """")
            If endPos > 0 Then
                val = Mid(json, startPos, endPos - startPos)
                ExtractEnv = "set " & keyName & "=" & val & " & "
            End If
        End If
    End If
End Function
