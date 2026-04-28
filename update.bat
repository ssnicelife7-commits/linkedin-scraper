@echo off
echo ============================================================
echo  LinkedIn Scraper — Update
echo ============================================================
echo.
echo  Pulling latest code from GitHub...
git pull
echo.
echo  Installing / updating Python packages...
pip install -r requirements.txt -q
echo.
echo ============================================================
echo  Done! Your scraper is up to date.
echo  You can close this window.
echo ============================================================
echo.
pause
