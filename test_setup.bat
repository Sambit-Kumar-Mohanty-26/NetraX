@echo off
REM NetraX Local Testing Setup Script
REM This script tests your complete setup before starting servers

echo.
echo ============================================================
echo NetraX - Complete System Setup Verification
echo ============================================================
echo.

REM Test 1: Check .env.local file
echo [1/4] Checking .env.local file...
if exist ".env.local" (
    echo ✅ .env.local file exists
    for /f "tokens=2 delims==" %%A in ('findstr "YOUTUBE_API_KEY" .env.local') do (
        if not "%%A"=="" (
            echo ✅ YOUTUBE_API_KEY is configured
        ) else (
            echo ❌ YOUTUBE_API_KEY is empty
            exit /b 1
        )
    )
) else (
    echo ❌ .env.local file not found
    exit /b 1
)

REM Test 2: Check Python
echo.
echo [2/4] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Install Python 3.8+ from python.org
    exit /b 1
) else (
    python --version
    echo ✅ Python installed
)

REM Test 3: Check Node.js
echo.
echo [3/4] Checking Node.js installation...
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js not found. Install from nodejs.org
    exit /b 1
) else (
    node --version
    echo ✅ Node.js installed
)

REM Test 4: Install Python dependencies
echo.
echo [4/4] Installing Python dependencies...
pip install python-dotenv --quiet >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Could not install python-dotenv automatically
    echo     Run: pip install python-dotenv
) else (
    echo ✅ Python dependencies installed
)

REM Summary
echo.
echo ============================================================
echo ✅ SETUP VERIFICATION COMPLETE
echo ============================================================
echo.
echo Next steps:
echo.
echo 1. Start Backend (Terminal 1):
echo    cd backend && npm install && npm run dev
echo.
echo 2. Start Frontend (Terminal 2):
echo    cd frontend && npm install && npm run dev
echo.
echo 3. Open http://localhost:3000 in your browser
echo.
echo 4. Upload a test video to test piracy detection
echo.
echo ============================================================
echo.
pause
