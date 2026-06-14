@echo off
setlocal enabledelayedexpansion

REM Root path of the repository
set ROOT=%~dp0
cd /d "%ROOT%"

REM Create virtual environment if missing
if not exist "%ROOT%\.venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    python -m venv "%ROOT%\.venv"
)

REM Install backend dependencies
if exist "%ROOT%\.venv\Scripts\python.exe" (
    echo Installing backend Python dependencies...
    "%ROOT%\.venv\Scripts\python.exe" -m pip install --upgrade pip
    "%ROOT%\.venv\Scripts\python.exe" -m pip install -r "%ROOT%backend\requirements.txt"
) else (
    echo ERROR: Python virtual environment not found and could not be created.
    pause
    exit /b 1
)

REM Install frontend dependencies if needed
if not exist "%ROOT%frontend\node_modules" (
    echo Installing frontend npm dependencies...
    pushd "%ROOT%frontend"
    npm install
    popd
)

REM Generate Prisma client if needed
echo Generating Prisma client...
"%ROOT%\.venv\Scripts\python.exe" -m prisma generate --schema="%ROOT%backend\prisma\schema.prisma"

REM Launch backend and frontend in separate windows
start "DocTalk Backend" cmd /k "cd /d "%ROOT%backend" && call "%ROOT%\.venv\Scripts\activate.bat" && uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000"
start "DocTalk Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev"

echo Dev environment started.
exit /b 0
