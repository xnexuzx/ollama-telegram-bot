@echo off
setlocal

REM ============================================================================
REM ==                   Ollama Telegram Bot Stop Script                      ==
REM ============================================================================

title Ollama Telegram Bot - Stopper

echo Searching for Ollama Telegram Bot process...

REM Find the Process ID (PID) of the bot by looking for the command line
set "PID="
for /f "tokens=2 delims==" %%a in ('wmic process where "name='pythonw.exe' and commandline like '%%bot\\run.py%%'" get processid /value 2^>nul') do (
    for /f "delims=" %%b in ("%%a") do (
        set "PID=%%b"
    )
)

if defined PID (
    echo Bot process found with PID: %PID%
    echo Stopping process...
    taskkill /F /PID %PID% >nul
    echo Bot stopped successfully.
) else (
    echo Bot process not found. It might not be running.
)

echo.
pause
exit /b 0