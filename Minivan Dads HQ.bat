@echo off
rem ============================================================
rem  Minivan Dads HQ - one-click CEO console
rem  Double-click me. Starts the dashboard (if it isn't already
rem  running) and opens it in your browser. To stop the server,
rem  close the minimized "Minivan Dads HQ" window on your taskbar.
rem ============================================================

set "PORT=8712"

rem Already running? Then just open the browser.
netstat -ano | findstr /r ":%PORT% .*LISTENING" >nul 2>&1
if %errorlevel%==0 goto open

start "Minivan Dads HQ" /min "%~dp0.venv\Scripts\brain.exe" dashboard --port %PORT%

rem Give the server a moment to come up.
timeout /t 3 /nobreak >nul

:open
start "" "http://127.0.0.1:%PORT%/"
exit /b 0
