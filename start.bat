@echo off
setlocal

REM ============================================================================
REM ==                  Ollama Telegram Bot Start Script                      ==
REM ============================================================================

title Ollama Telegram Bot - Runner

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"

REM Change to the project directory
cd /d "%SCRIPT_DIR%"

REM Check if virtual environment exists
if exist ".venv\Scripts\pythonw.exe" goto :check_env
echo [ERROR] pythonw.exe not found in the virtual environment!
echo Please try running Setup.bat again.
pause
exit /b 1

:check_env
REM Check if .env file exists
if exist ".env" goto :start_bot
echo [ERROR] Configuration file (.env) not found!
echo Please run Setup.bat first to create it.
pause
exit /b 1

:start_bot
echo Starting Ollama Telegram Bot in the background...

REM Using pythonw.exe to run without a console window (silent mode)
REM /B flag runs in the background, /LOW sets low CPU priority
start /B /LOW /MIN "" ".venv\Scripts\pythonw.exe" "bot\run.py"

echo Bot started successfully. It is now running in the background.
echo To stop it, please run stop.bat

REM A short pause to allow the user to read the message
timeout /t 3 /nobreak >nul

REM A short pause to allow the user to read the message
timeout /t 3 /nobreak >nul

exit /b 0