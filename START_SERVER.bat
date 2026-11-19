@echo off
title CogMonitor - Flask Server
cd /d "%~dp0"
color 0A

echo.
echo  ============================================
echo   CogMonitor - Starting Server (XAMPP)
echo  ============================================
echo.

REM --- Step 1: Check XAMPP MySQL is running ---
echo  [1] Checking XAMPP MySQL...
netstat -ano | findstr ":3306" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    color 0C
    echo.
    echo  [ERROR] XAMPP MySQL is NOT running!
    echo.
    echo  Open XAMPP Control Panel and click START on MySQL.
    echo  Then run this file again.
    echo.
    pause
    exit /b 1
)
echo       OK - MySQL running on port 3306
echo.

REM --- Step 2: Find Python ---
echo  [2] Looking for Python...
set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%PATH%"
set "PATH=%LocalAppData%\Programs\Python\Python313;%LocalAppData%\Programs\Python\Python313\Scripts;%PATH%"
set "PATH=%LocalAppData%\Programs\Python\Python311;%LocalAppData%\Programs\Python\Python311\Scripts;%PATH%"

set "PY="
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PY=%LocalAppData%\Programs\Python\Python313\python.exe"
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PY=%LocalAppData%\Programs\Python\Python311\python.exe"

if not defined PY (
    where python >nul 2>&1
    if %errorlevel%==0 (
        for /f "delims=" %%i in ('where python ^| findstr /v WindowsApps') do set "PY=%%i"
    )
)

if not defined PY (
    color 0C
    echo.
    echo  [ERROR] Python is not installed!
    echo.
    echo  XAMPP runs MySQL only. This website also needs Python + Flask.
    echo  Double-click INSTALL_PYTHON.bat, install Python, restart PC,
    echo  then run SETUP_EVERYTHING.bat once.
    echo.
    pause
    exit /b 1
)
echo       OK - %PY%
echo.

REM --- Step 3: Install packages if missing ---
echo  [3] Checking Flask packages...
"%PY%" -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo       Installing packages (first time only)...
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        color 0C
        echo  [ERROR] Failed to install packages.
        pause
        exit /b 1
    )
)
echo       OK - packages ready
echo.

REM --- Step 4: Check / create database ---
echo  [4] Checking database...
"%PY%" -c "import pymysql; c=pymysql.connect(host='localhost',user='root',password='',database='cognitive_monitoring_db'); c.close()" >nul 2>&1
if errorlevel 1 (
    echo       Setting up database (first time only)...
    "%PY%" init_db.py
    if errorlevel 1 (
        color 0C
        echo  [ERROR] Database setup failed. Is XAMPP MySQL running?
        pause
        exit /b 1
    )
)
echo       OK - database ready
echo.

REM --- Step 5: Preflight check (packages, DB, migrations) ---
echo  [5] Running preflight check...
"%PY%" preflight.py
if errorlevel 1 (
    color 0C
    echo.
    echo  [ERROR] Preflight failed. Fix the issue above, then run again.
    echo  Or try: SETUP_EVERYTHING.bat
    echo.
    pause
    exit /b 1
)
echo.

echo  ============================================
echo   Starting Flask server on port 5000...
echo.
echo   Your website URLs:
echo     Welcome:   http://127.0.0.1:5000
echo     Login:     http://127.0.0.1:5000/login
echo     Register:  http://127.0.0.1:5000/register
echo.
echo   XAMPP MySQL = database (port 3306)
echo   Flask       = website  (port 5000)
echo.
echo   KEEP THIS WINDOW OPEN while using the site.
echo   Press Ctrl+C to stop the server.
echo  ============================================
echo.

REM Open browser after a short delay (server needs a moment to start)
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"

"%PY%" run.py
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo  Server failed to start.
    echo  Try running SETUP_EVERYTHING.bat once.
    echo.
    pause
)
