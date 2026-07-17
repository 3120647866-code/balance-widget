@echo off
:: Install API 余额小组件到开机自启
:: 右键 → 以管理员身份运行 或直接双击

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS_PATH=D:\app\balance-widget\start_widget.vbs"
set "SHORTCUT=%STARTUP_DIR%\API余额小组件.lnk"

echo ============================================
echo   API 余额小组件 — 开机自启安装
echo ============================================
echo.

:: Create VBS shortcut in startup folder
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%SHORTCUT%'); $sc.TargetPath = '%VBS_PATH%'; $sc.WorkingDirectory = 'D:\app\balance-widget'; $sc.WindowStyle = 7; $sc.Description = 'API 余额桌面小组件'; $sc.Save()"

if %ERRORLEVEL% EQU 0 (
    echo [OK] 已添加到开机自启
    echo.
    echo 快捷方式: %SHORTCUT%
) else (
    echo [FAIL] 添加失败，请检查权限
    pause
    exit /b 1
)

echo [OK] 安装完成！下次开机自动启动。
echo.
echo 现在可以手动启动:
echo   start "" "%VBS_PATH%"
echo.
pause
