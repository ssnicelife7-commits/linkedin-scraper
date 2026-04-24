@echo off
echo ============================================================
echo  LinkedIn Scraper - One-Time Setup
echo ============================================================
echo.

REM Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo IMPORTANT: During install, check "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo [+] Python found.
echo.

REM Install dependencies
echo [*] Installing required packages...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install packages.
    pause
    exit /b 1
)

echo.
echo [*] Installing Playwright browser (Chromium)...
python -m playwright install chromium
if errorlevel 1 (
    echo [ERROR] Failed to install Playwright browser.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Setup complete!
echo.
echo  NEXT STEPS:
echo  1. Export your LinkedIn cookies (see cookies\README.txt)
echo  2. Add your post URLs to input\post_urls.csv
echo  3. Run run_scraper.bat to start scraping
echo ============================================================
echo.
pause
