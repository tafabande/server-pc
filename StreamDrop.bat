@echo off
setlocal EnableDelayedExpansion
title StreamDrop - LAN Hub Setup ^& Launch

echo.
echo  +--------------------------------------+
echo  :        StreamDrop - LAN Hub          :
echo  :     Unified Stream + Share Server    :
echo  +--------------------------------------+
echo.

:: --- 1. Environment Variables ---
set "SHARED_FOLDER=%~dp0"
if "%SHARED_FOLDER:~-1%"=="\" set "SHARED_FOLDER=%SHARED_FOLDER:~0,-1%"
echo  [*] Target Shared Folder: %SHARED_FOLDER%

set "SERVER_DIR=C:\Users\User\Desktop\server"
set "PORT=8000"

:: --- 2. Network Check ---
echo  [*] Checking network connection...
ping -n 1 8.8.8.8 >nul 2>&1
if !errorlevel! neq 0 (
    echo  [!] WARNING: No active internet connection detected.
    echo      StreamDrop will still work locally, but devices must be on the same WiFi.
    echo      Ensure your router is active and devices are connected to it.
    echo.
) else (
    echo  [OK] Network is connected.
)

:: --- 3. Python Check ---
echo  [*] Checking for Python...
where py >nul 2>&1 && (set PYTHON=py) || (
    where python >nul 2>&1 && (set PYTHON=python) || (
        echo.
        echo  [ERROR] Python is not installed or not in PATH!
        echo  [FIX]   Download Python 3.10+ from: https://www.python.org/downloads/
        echo          IMPORTANT: Check the box "Add Python to PATH" during installation.
        echo.
        pause
        exit /b 1
    )
)
echo  [OK] Python found.

:: --- 4. FFmpeg Check ---
echo  [*] Checking for FFmpeg (Required for Media Optimization ^& HLS)...
where ffmpeg >nul 2>&1
if !errorlevel! neq 0 (
    echo.
    echo  [!] WARNING: FFmpeg is missing. 
    echo      The server will still launch perfectly fine, but the "Media Optimization" 
    echo      and HLS background streaming features will be disabled.
    echo      You can always add it later if you need those features.
    echo.
) else (
    echo  [OK] FFmpeg found.
)

:: --- 5. Dependencies Check ---
echo  [*] Checking Python dependencies...
cd /d "%SERVER_DIR%"
%PYTHON% -c "import fastapi, uvicorn, aiofiles" >nul 2>&1
if !errorlevel! neq 0 (
    echo  [!] Missing dependencies. Attempting to install from requirements.txt...
    %PYTHON% -m pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo.
        echo  [ERROR] Failed to install dependencies.
        echo  [FIX]   Ensure you have an active internet connection or try running:
        echo          pip install -r "%SERVER_DIR%\requirements.txt" manually.
        echo.
        pause
        exit /b 1
    )
    echo  [OK] Dependencies installed successfully.
) else (
    echo  [OK] Dependencies are up to date.
)

:: --- 6. Port Check ---
echo  [*] Checking if port %PORT% is available...
netstat -ano | findstr LISTENING | findstr ":%PORT%" >nul
if !errorlevel! equ 0 (
    echo.
    echo  [!] WARNING: Port %PORT% is currently occupied by another process!
    echo      The server will attempt to forcefully kill the blocking process.
    echo      If StreamDrop still fails to start, you may need to find the process using:
    echo      "netstat -ano | findstr :%PORT%" and kill it via Task Manager.
    echo.
) else (
    echo  [OK] Port %PORT% is free.
)

:: --- 7. Launch Server ---
echo.
echo  [*] All checks passed! Starting StreamDrop modular server...
echo.
%PYTHON% run.py

:: If the server crashes or closes, pause to show the error
if !errorlevel! neq 0 (
    echo.
    echo  [ERROR] The server crashed or failed to start.
    echo  [FIX]   Review the error output above. If it's a module error, run:
    echo          pip install -r requirements.txt
    echo.
)
pause
