@echo off
REM HealthPulse Web Server Runner

cd /d "C:\GIT\HealthPulse"

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run web server
echo Starting HealthPulse Web Server...
echo Access at: http://localhost:8000
echo Press Ctrl+C to stop

python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload

deactivate
