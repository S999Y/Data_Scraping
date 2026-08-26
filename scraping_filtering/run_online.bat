@echo off
echo ============================================
echo   AI Professor Filter - Online Demo
echo ============================================
echo.
echo This mode fetches fresh data from OpenAlex API.
echo It may take several minutes depending on the
echo number of professors.
echo.

cd /d "%~dp0"

echo [1/3] Installing dependencies...
pip install -q pandas requests >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies. Make sure Python and pip are installed.
    pause
    exit /b 1
)

echo [2/3] Fetching professor data from OpenAlex API...
echo       (Demo mode: enriching 10 professors, takes ~30 seconds)
echo.
python openalex_fetcher.py --limit 10 --delay 0.15
echo.

if %errorlevel% neq 0 (
    echo ERROR: OpenAlex fetcher failed.
    pause
    exit /b 1
)

echo [3/3] Running merge script...
echo.
python merge_ai_professors.py
echo.

if %errorlevel% neq 0 (
    echo ERROR: Merge script failed.
    pause
    exit /b 1
)

echo ============================================
echo   Done! Output: merged_ai_professors.csv
echo ============================================
echo.
pause
