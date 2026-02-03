@echo off
REM HealthPulse Daily Full Runner
REM This script runs the complete daily job (crawling + analysis + send)
REM Use this for manual full execution or testing

cd /d "C:\GIT\HealthPulse"

REM Activate virtual environment and run
call venv\Scripts\activate.bat

REM Run the full daily job
python src/main.py --run-once

REM Log completion
echo [%date% %time%] Daily full job completed >> logs\scheduler.log

deactivate
