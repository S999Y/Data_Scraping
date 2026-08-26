@echo off
echo ============================================
echo   AI Professor Filter - Offline Demo
echo ============================================
echo.

cd /d "%~dp0"

echo [1/2] Installing dependencies...
pip install -q pandas >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Failed to install pandas. Make sure Python and pip are installed.
    pause
    exit /b 1
)

echo [2/2] Running merge script...
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
