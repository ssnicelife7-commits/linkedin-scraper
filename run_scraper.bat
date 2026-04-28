@echo off
echo ============================================================
echo  LinkedIn Engager Scraper
echo ============================================================
echo.
echo  FIRST TIME ONLY:
echo    Export all cookies from Opera using Cookie-Editor
echo    and save as cookies\linkedin_cookies.json
echo    See cookies\README.txt for step-by-step instructions.
echo.
echo  NORMAL RUNS:
echo    Just run this script. No cookie export needed.
echo    The browser window will open and scrape automatically.
echo    Do NOT close the browser window while it's running.
echo.

python src\scraper.py

echo.
echo ============================================================
echo  Session finished. Check output\ for your results.
echo  Run this script again to process the next batch of posts.
echo ============================================================
echo.
pause
