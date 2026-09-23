@echo off
title NonRoot Setup - Windows
echo ==============================================
echo   NonRoot Autonomous AI Agent - Windows Setup
echo ==============================================

powershell -ExecutionPolicy Bypass -File "%~dp0install_windows_shortcut.ps1"

echo.
echo [OK] Setup completed successfully!
pause
