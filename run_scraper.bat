@echo off
echo ============================================================
echo  LinkedIn Engager Scraper
echo ============================================================
echo.
echo  This will open a Chrome window and scrape up to 30 posts.
echo  Do NOT close the Chrome window while it's running.
echo  You CAN watch what it's doing — that's normal.
echo.

python src\scraper.py

echo.
echo ============================================================
echo  Session finished. Check output\ for your results.
echo  Run this script again to process the next batch of posts.
echo ============================================================
echo.
pause
