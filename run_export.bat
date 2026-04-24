@echo off
echo ============================================================
echo  Engager Deduplicator + Scorer
echo ============================================================
echo.
echo  This merges all your scraping sessions, removes duplicates,
echo  and ranks everyone by engagement strength.
echo.
echo  Run this AFTER you have finished all your scraping sessions.
echo.

python src\dedup_export.py

echo.
echo ============================================================
echo  Export complete. Upload output\FINAL_engagers_ranked.csv
echo  to Apollo.io for ICP filtering.
echo ============================================================
echo.
pause
