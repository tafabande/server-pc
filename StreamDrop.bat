@echo off
title StreamDrop - LAN Hub

echo.
echo  +--------------------------------------+
echo  :        StreamDrop - LAN Hub          :
echo  :     Unified Stream + Share Server    :
echo  +--------------------------------------+
echo.

:: This folder becomes the shared media folder
set "SHARED_FOLDER=%~dp0"
echo  [*] Serving folder: %SHARED_FOLDER%

:: Kill any existing StreamDrop on port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000.*LISTENING" 2^>nul') do (
    echo  [*] Closing previous instance (PID %%a)...
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: Server install location (edit this once after install)
set "SERVER_DIR=C:\Users\User\Desktop\server"

:: Auto-detect Python
where py >nul 2>&1 && (set PYTHON=py) || (
    where python >nul 2>&1 && (set PYTHON=python) || (
        echo [ERROR] Python not found. Install Python 3.10+ first.
        pause
        exit /b 1
    )
)

echo  [*] Starting StreamDrop...
echo.
%PYTHON% "%SERVER_DIR%\main.py"
pause
