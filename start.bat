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

REM 1. Check Python Installation
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan di sistem Anda!
    echo Harap install Python 3.10 atau versi di atasnya.
    echo WAJIB centang "Add Python to PATH" saat menginstall.
    echo Download: https://www.python.org/downloads/
    echo.
    pause
    exit /b
)

REM 2. Check Node.js / NPM Installation
where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js / NPM tidak ditemukan di sistem Anda!
    echo Harap install Node.js terlebih dahulu untuk menjalankan Frontend.
    echo Download: https://nodejs.org/ - Pilih versi LTS
    echo.
    pause
    exit /b
)

REM 3. Check for GitHub Updates
where git >nul 2>nul
if not errorlevel 1 (
    echo [System] Mengecek update terbaru dari GitHub...
    git pull origin main
) else (
    echo [System] Git tidak terdeteksi. Melewati pengecekan update otomatis dari GitHub.
)
echo.

REM Check if Python venv exists
if not exist ".venv" (
    echo [System] Virtual environment tidak ditemukan. Membuat .venv...
    python -m venv .venv
    
    echo [System] Menginstall kebutuhan Backend Harap tunggu...
    call .venv\Scripts\activate
    python -m pip install --upgrade pip
    pip install fastapi uvicorn playwright websockets pydantic requests google-generativeai Pillow
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
start /b cmd /c "cd frontend && npm run dev -- --port 5115"

echo [System] Mengecek proses lama yang masih nyangkut di port 8001/9227...
for %%P in (8001 9227) do (
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr /r /c:"127.0.0.1:%%P .*LISTENING"') do (
        echo [System] Menutup proses lama ^(PID %%A^) di port %%P...
        taskkill /F /PID %%A >nul 2>nul
    )
)

echo [System] Menyiapkan browser... (Mohon tunggu sebentar)
ping 127.0.0.1 -n 4 > nul
start http://localhost:5115

echo [System] Menjalankan Backend Engine...
call .venv\Scripts\activate
".venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8001

pause
