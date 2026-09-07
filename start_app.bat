@echo off
title Audio Sync Tool
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================================
echo   Audio-Video Sync Tool - Khoi dong Local Server
echo ========================================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_server.py
) else (
    python run_server.py
)

pause
