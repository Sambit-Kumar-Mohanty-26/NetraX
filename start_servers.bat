@echo off
REM NetraX - Start Backend and Frontend Servers
REM Opens two terminal windows for backend and frontend development

echo.
echo ============================================================
echo 🚀 NetraX - Starting Local Development Servers
echo ============================================================
echo.

REM Check if .env.local exists
if not exist ".env.local" (
    echo ❌ ERROR: .env.local not found
    echo Please run test_setup.bat first
    pause
    exit /b 1
)

echo Preparing to start servers...
echo.

REM Start Backend in new window
echo [1/2] Starting Backend (http://localhost:5000)
start "NetraX Backend" cmd /k "cd backend && npm install && npm run dev"

REM Wait a bit before starting frontend
timeout /t 3 /nobreak

REM Start Frontend in new window
echo [2/2] Starting Frontend (http://localhost:3000)
start "NetraX Frontend" cmd /k "cd frontend && npm install && npm run dev"

echo.
echo ============================================================
echo ✅ Servers Starting...
echo ============================================================
echo.
echo 🔗 Frontend: http://localhost:3000
echo 🔗 Backend:  http://localhost:5000
echo.
echo 📝 Both terminal windows will show detailed logs
echo 🎬 Upload a video to test piracy detection
echo.
echo Press Ctrl+C in each terminal to stop
echo.
pause
