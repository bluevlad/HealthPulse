@echo off
REM HealthPulse Newsletter Sender (8:00 AM)
REM This script sends the daily newsletter

cd /d "C:\GIT\HealthPulse"

REM Activate virtual environment and run
call venv\Scripts\activate.bat

REM Run send job
python src/main.py --send-only

REM Log completion
echo [%date% %time%] Newsletter send job completed >> logs\scheduler.log

deactivate
