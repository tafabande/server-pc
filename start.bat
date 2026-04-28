@echo off
title StreamDrop — LAN Hub
echo.
echo  ╔══════════════════════════════════════╗
echo  ║        StreamDrop — LAN Hub          ║
echo  ║     Unified Stream ^& Share Server    ║
echo  ╚══════════════════════════════════════╝
echo.

:: Auto-detect Python
where py >nul 2>&1 && (set PYTHON=py) || (
    where python >nul 2>&1 && (set PYTHON=python) || (
        echo [ERROR] Python not found. Install Python 3.10+ first.
        pause
        exit /b 1
    )
)

:: Install deps if needed
%PYTHON% -m pip install -r requirements.txt --quiet 2>nul

:: Launch
%PYTHON% main.py
pause
