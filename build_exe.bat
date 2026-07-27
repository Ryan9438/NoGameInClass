@echo off
chcp 65001 >nul
echo ========================================
echo   NoGameInClass - 打包成单文件 exe
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 没找到 Python，先装 Python 再来
    pause
    exit /b 1
)

REM 装依赖
echo [*] 安装依赖...
pip install -r requirements.txt
pip install pyinstaller

REM 打包
echo [*] 打包中...
pyinstaller --onefile --console ^
    --name "NoGameInClass" ^
    --add-data "src/data;src/data" ^
    --add-data "config.json;." ^
    --distpath "." ^
    src/main.py

if %errorlevel% equ 0 (
    echo.
    echo [✓] 打包成功！NoGameInClass.exe 已经躺在当前目录了
    echo     拔下 U 盘，拿起 exe，去学校嗨吧
) else (
    echo [!] 打包失败了，看看上面报的啥错
)

pause
