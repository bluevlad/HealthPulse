@echo off
REM HealthPulse Daily Newsletter Runner
REM This script runs the daily news collection, analysis, and email delivery

cd /d "C:\GIT\HealthPulse"

REM Activate virtual environment and run
call venv\Scripts\activate.bat

REM Run the daily job
python src/main.py --run-once

REM Log completion
echo [%date% %time%] Daily job completed >> logs\scheduler.log

deactivate
