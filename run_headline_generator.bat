@echo off
cd /d "%~dp0"
if "%ANTHROPIC_API_KEY%"=="" (
    echo ERROR: ANTHROPIC_API_KEY is not set.
    echo Set it via: set ANTHROPIC_API_KEY=sk-ant-...
    pause
    exit /b 1
)
python app.py
pause
