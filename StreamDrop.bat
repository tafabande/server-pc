@echo off
title StreamDrop - LAN Hub

echo.
echo  +--------------------------------------+
echo  :        StreamDrop - LAN Hub          :
echo  :     Unified Stream + Share Server    :
echo  +--------------------------------------+
echo.

:: 1. Define the folder to share (wherever this .bat file is placed)
set "SHARED_FOLDER=%~dp0"
if "%SHARED_FOLDER:~-1%"=="\" set "SHARED_FOLDER=%SHARED_FOLDER:~0,-1%"
echo  [*] Serving folder: %SHARED_FOLDER%

:: 2. Define the fixed location of the StreamDrop server code
set "SERVER_DIR=C:\Users\User\Desktop\server"

:: 3. Auto-detect Python
where py >nul 2>&1 && (set PYTHON=py) || (
    where python >nul 2>&1 && (set PYTHON=python) || (
        echo [ERROR] Python not found. Install Python 3.10+ first.
        pause
        exit /b 1
    )
)

:: 4. Start the server
echo  [*] Starting StreamDrop...
echo.
cd /d "%SERVER_DIR%"
%PYTHON% main.py
pause
