@echo off
title StreamDrop - LAN Hub
cd /d "%~dp0"

echo.
echo  +--------------------------------------+
echo  :        StreamDrop - LAN Hub          :
echo  :     Unified Stream + Share Server    :
echo  +--------------------------------------+
echo.

:: Auto-detect Python
where py >nul 2>&1 && (set PYTHON=py) || (
    where python >nul 2>&1 && (set PYTHON=python) || (
        echo [ERROR] Python not found. Install Python 3.10+ first.
        pause
        exit /b 1
    )
)

echo  [*] Checking dependencies...
%PYTHON% -m pip install -r requirements.txt --quiet 2>nul

echo  [*] Starting StreamDrop...
echo.
%PYTHON% main.py
pause
