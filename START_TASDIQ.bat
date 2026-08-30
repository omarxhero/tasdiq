@echo off
cd /d "%~dp0"
echo ============================================
echo   TASDIQ - starting demo server...
echo   Leave this window OPEN while demoing.
echo ============================================
start "" http://127.0.0.1:8793/
python -m uvicorn app.main:app --port 8793
pause
