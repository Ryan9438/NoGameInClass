@echo off
chcp 65001 >nul
title NoGameInClass - 整治游戏狗

echo ========================================
echo      ____          ____        _   _    _
echo     / \ \        / /  _ \    / \ | \  / |
echo    / _ \ \  /\  / /| |_) |  / _ \|  \/  |
echo   / ___ \ \/  \/ / |  _ <  / ___ \ |\/| |
echo  /_/   \_\__/\__/  |_| \_\/_/   \_\_|  |_|
echo.
echo            NoGameInClass v1.0
echo        整治游戏狗，还我清净网络
echo ========================================
echo.

REM 检查管理员权限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 需要管理员权限才能运行！
    echo     右键点击 "启动.bat"，选择 "以管理员身份运行"
    pause
    exit /b 1
)

echo [*] 启动 NoGameInClass...
echo [*] 按 Ctrl+C 随时停止（游戏狗们会感谢你的）

python src/main.py

if %errorlevel% neq 0 (
    echo.
    echo [!] 出错了，检查一下是不是装了依赖：
    echo     pip install -r requirements.txt
)

pause
