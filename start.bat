@echo off
title Affilia PinShop - Engine Terminal
color 0B

echo.
echo     ___    __________________    ________  ___ 
echo    /   ^|  / ____/ ____/  _/ /   /  _/ __ ^|/   ^|
echo   / /^| ^| / /_  / /_   / // /    / // /_/ / /^| ^|
echo  / ___ ^|/ __/ / __/ _/ // /____/ // __  / ___ ^|
echo /_/  ^|_/_/   /_/   /___/_____/___/_/ ^|_/_/  ^|_^|
echo.
echo ====================================================
echo        PINSHOP EDITION - AUTO PINTEREST PIN
echo ====================================================
echo.
REM Check if Python venv exists
if not exist ".venv" (
    echo [System] Virtual environment tidak ditemukan. Membuat .venv...
    python -m venv .venv
    
    echo [System] Menginstall kebutuhan Backend Harap tunggu...
    call .venv\Scripts\activate
    pip install fastapi uvicorn playwright websockets pydantic requests google-generativeai
    playwright install chromium
) else (
    echo [System] Virtual environment ditemukan.
)

REM Check if frontend node_modules exists
if not exist "frontend\node_modules" (
    echo [System] Menginstall kebutuhan Frontend Harap tunggu...
    cd frontend
    call npm install
    cd ..
) else (
    echo [System] Dependensi Frontend ditemukan.
)

echo.
echo [System] Memulai UI (Frontend) di background...
start /b cmd /c "cd frontend && npm run dev"

echo [System] Mengecek proses lama yang masih nyangkut di port 8001/9227...
for %%P in (8001 9227) do (
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr /r /c:"127.0.0.1:%%P .*LISTENING"') do (
        echo [System] Menutup proses lama ^(PID %%A^) di port %%P...
        taskkill /F /PID %%A >nul 2>nul
    )
)

echo [System] Menyiapkan browser... (Mohon tunggu sebentar)
timeout /t 3 /nobreak > nul
start http://localhost:5173

echo [System] Menjalankan Backend Engine...
call .venv\Scripts\activate
".venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8001

pause
