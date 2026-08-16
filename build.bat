@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo   ETNet Futures Exporter - Windows 一鍵打包工具
echo   (需要 Python 3.9+ 已安裝並加入 PATH)
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [錯誤] 找不到 Python。請先到 https://www.python.org/downloads/
    echo        安裝 Python 3.9 或以上版本，安裝時記得勾選
    echo        "Add python.exe to PATH"。
    pause
    exit /b 1
)

echo [1/3] 安裝相依套件 ...
python -m pip install --upgrade pip || goto :fail
python -m pip install -r requirements.txt pyinstaller || goto :fail

echo [2/3] 執行 PyInstaller 打包 ...
python -m PyInstaller --clean --noconfirm futures_exporter.spec || goto :fail

echo [3/3] 完成!
echo.
echo     exe 已產生: dist\ETNetFuturesExporter.exe
echo.
pause
exit /b 0

:fail
echo.
echo [錯誤] 打包失敗，請檢查上方錯誤訊息。
pause
exit /b 1
