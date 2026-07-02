@echo off
title TMPVL Billing Audit System - Control Panel
color 0b

echo =======================================================================
echo         TMPVL BILLING AUDIT ^& FRAUD DETECTION SYSTEM CONTROL PANEL
echo =======================================================================
echo.
echo [1/3] Activating virtual environment and starting FastAPI backend...
start "TMPVL Backend Service" cmd /k "call .venv\Scripts\activate && set PYTHONPATH=. && python -m backend.main"

echo [2/3] Starting Vite/React Frontend development server...
start "TMPVL Frontend Client" cmd /k "cd frontend && npm run dev"

echo [3/3] Launching web browser...
timeout /t 3 /nobreak > nul
start http://localhost:5173/

echo.
echo =======================================================================
echo  System is running. Close the spawned windows to stop services.
echo =======================================================================
echo.
pause
