@echo off
TITLE Nexus ASM Backend Server
color 0A

echo ===================================================
echo      Nexus ASM - Facebook Automation Assistant
echo ===================================================
echo.

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 goto NoPython

:: Create VENV if it doesn't exist
if not exist "venv" (
    echo [INFO] Creating Virtual Environment...
    python -m venv venv
)

:: Activate VENV
echo [INFO] Activating Virtual Environment...
call venv\Scripts\activate.bat

:: Install Dependencies
echo [INFO] Installing Dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 goto InstallFailed

:: Start Server
echo.
echo [SUCCESS] Server is Ready!
echo [INFO] Opening Dashboard...
start http://localhost:8000
echo.
echo [LOGS] Server Output:
echo ---------------------------------------------------
uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause
exit /b

:NoPython
echo [ERROR] Python is not installed or not in PATH.
pause
exit /b

:InstallFailed
echo [ERROR] Failed to install dependencies.
pause
exit /b
