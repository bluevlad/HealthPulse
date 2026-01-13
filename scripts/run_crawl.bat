@echo off
REM HealthPulse Crawling Runner (7:00 AM)
REM This script runs news collection and AI analysis

cd /d "C:\GIT\HealthPulse"

REM Activate virtual environment and run
call venv\Scripts\activate.bat

REM Run crawling job (collect + process)
python src/main.py --collect-only
python src/main.py --process-only

REM Log completion
echo [%date% %time%] Crawling job completed >> logs\scheduler.log

deactivate
