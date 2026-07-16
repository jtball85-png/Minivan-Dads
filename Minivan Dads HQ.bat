@echo off
rem ============================================================
rem  Minivan Dads HQ - one-click CEO console
rem  Double-click me. Starts the dashboard (if it isn't already
rem  running) and opens it in your browser. To stop the server,
rem  close the minimized "Minivan Dads HQ" window on your taskbar.
rem  Server output is written to dashboard.log in this folder.
rem ============================================================

set "PORT=8712"
cd /d "%~dp0"

rem Already running? Then just open the browser. (/c: keeps the pattern
rem whole - without it findstr treats the space as OR and always matches.)
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul 2>&1
if %errorlevel%==0 goto open

start "Minivan Dads HQ" /min cmd /c ".venv\Scripts\brain.exe dashboard --port %PORT% >> dashboard.log 2>&1"

rem Give the server a moment to come up (ping = stdin-free sleep).
ping -n 4 127.0.0.1 >nul

:open
start "" "http://127.0.0.1:%PORT%/"
exit /b 0
