@echo off
cd /d "%~dp0"
echo ============================================
echo   TASDIQ - starting demo server...
echo ============================================
rem kill any old instance holding port 8793
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8793 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
timeout /t 1 /nobreak >nul
start "" http://127.0.0.1:8793/
python -m uvicorn app.main:app --port 8793
pause
