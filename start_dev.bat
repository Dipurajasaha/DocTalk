@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

rem ------------------------------------------------------------
rem DocTalk local development starter (SIMPLIFIED)
rem
rem Removed: Docker, MySQL, Adminer, Ollama, Streamlit checks
rem Database: Supabase PostgreSQL (external, no local setup needed)
rem ------------------------------------------------------------

call :init_colors
call :banner

set "ROOT=%CD%"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"

call :info "[1/5] Infrastructure checks"

if not exist ".env" (
    call :warn "Missing .env in project root. Copy .env.example to .env before first run."
) else (
    call :ok "Found .env"
)

if not exist ".venv\Scripts\activate.bat" (
    set "VENV_OK=0"
    call :warn "Missing Python virtual environment at .venv. Backend will use system python if available."
) else (
    set "VENV_OK=1"
    call :ok "Found Python virtual environment"
)

if not exist "backend\main.py" (
    call :err "Missing backend\main.py. Cannot start backend."
    exit /b 1
)

if not exist "frontend\package.json" (
    call :err "Missing frontend\package.json. Cannot start frontend."
    exit /b 1
)

call :detect_frontend_pm
if errorlevel 1 exit /b 1

call :pick_frontend_port
if errorlevel 1 exit /b 1

if not exist "frontend\node_modules" (
    set "NEED_FRONTEND_INSTALL=1"
    call :warn "frontend\node_modules is missing. Will run install first."
) else (
    set "NEED_FRONTEND_INSTALL=0"
    call :ok "Frontend dependencies directory exists"
)

call :info "[2/5] Checking Gemini API configuration"
set "GEMINI_READY=0"
if not exist ".env" (
    call :warn "Missing .env. Copy .env.example and set GEMINI_API_KEY for AI features."
) else (
    findstr /I /B "GEMINI_API_KEY=" ".env" | findstr /V /I "your_gemini_api_key_here" >nul 2>&1
    if errorlevel 1 (
        call :warn "GEMINI_API_KEY is missing or still a placeholder. AI features may fall back or fail."
    ) else (
        set "GEMINI_READY=1"
        call :ok "GEMINI_API_KEY is configured"
    )
)

call :info "[3/5] Starting backend and frontend"

set "DOCTALK_ROOT=%ROOT%"
set "DOCTALK_BACKEND_EXE=C:\Program Files\Python312\python.exe"
set "DOCTALK_BACKEND_ARGS=-m uvicorn backend.main:app --reload --reload-dir backend --host 127.0.0.1 --port %BACKEND_PORT%"
set "DOCTALK_BACKEND_PORT=%BACKEND_PORT%"
set "DOCTALK_FRONTEND_DIR=%ROOT%\frontend"
set "DOCTALK_FRONTEND_INSTALL_CMD=%FE_INSTALL_CMD%"
set "DOCTALK_FRONTEND_DEV_CMD=%FE_DEV_CMD%"
set "DOCTALK_FRONTEND_PORT=%FRONTEND_PORT%"
set "DOCTALK_NEED_FRONTEND_INSTALL=%NEED_FRONTEND_INSTALL%"
set "DOCTALK_RUN_ID=%RANDOM%%RANDOM%"
call :orchestrate
exit /b %errorlevel%

:init_colors
for /f %%e in ('echo prompt $E ^| cmd') do set "ESC=%%e"
set "C_RESET=%ESC%[0m"
set "C_RED=%ESC%[91m"
set "C_GREEN=%ESC%[92m"
set "C_YELLOW=%ESC%[93m"
set "C_CYAN=%ESC%[96m"
exit /b 0

:banner
echo.
echo ==============================================================
echo   DocTalk Local Development Starter (Supabase PostgreSQL)
echo ==============================================================
echo.
exit /b 0

:info
echo %C_CYAN%[INFO]%C_RESET% %~1
exit /b 0

:ok
echo %C_GREEN%[ OK ]%C_RESET% %~1
exit /b 0

:warn
echo %C_YELLOW%[WARN]%C_RESET% %~1
exit /b 0

:err
echo %C_RED%[ERR ]%C_RESET% %~1
exit /b 0

:detect_frontend_pm
set "FE_PM="
set "FE_INSTALL_CMD="
set "FE_DEV_CMD="

if exist "frontend\pnpm-lock.yaml" (
    where pnpm >nul 2>&1
    if errorlevel 1 (
        call :err "Detected pnpm lockfile but pnpm is not installed."
        exit /b 1
    )
    set "FE_PM=pnpm"
    set "FE_INSTALL_CMD=pnpm install"
    set "FE_DEV_CMD=pnpm dev"
)

if not defined FE_PM if exist "frontend\yarn.lock" (
    where yarn >nul 2>&1
    if errorlevel 1 (
        call :err "Detected yarn lockfile but yarn is not installed."
        exit /b 1
    )
    set "FE_PM=yarn"
    set "FE_INSTALL_CMD=yarn install"
    set "FE_DEV_CMD=yarn dev"
)

if not defined FE_PM if exist "frontend\package-lock.json" (
    where npm >nul 2>&1
    if errorlevel 1 (
        call :err "Detected npm lockfile but npm is not installed."
        exit /b 1
    )
    set "FE_PM=npm"
    set "FE_INSTALL_CMD=npm install"
    set "FE_DEV_CMD=npm run dev"
)

if not defined FE_PM (
    where npm >nul 2>&1
    if errorlevel 1 (
        call :err "No lockfile detected and npm is unavailable. Cannot start frontend."
        exit /b 1
    )
    set "FE_PM=npm"
    set "FE_INSTALL_CMD=npm install"
    set "FE_DEV_CMD=npm run dev"
)

call :ok "Frontend package manager detected: %FE_PM%"
exit /b 0

:pick_frontend_port
for /L %%P in (5173,1,5183) do (
    netstat -ano | findstr /R /C:":%%P .*LISTENING" >nul 2>&1
    if errorlevel 1 (
        if not "%%P"=="!FRONTEND_PORT!" call :warn "Frontend port !FRONTEND_PORT! is already in use. Using %%P instead."
        set "FRONTEND_PORT=%%P"
        call :ok "Frontend port selected: !FRONTEND_PORT!"
        exit /b 0
    )
)
call :err "No free frontend port found in the 5173-5183 range."
exit /b 1

:orchestrate
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $root=$env:DOCTALK_ROOT; $backend=$null; $frontend=$null; $shutdown=$false; $backendReady=$false; $frontendReady=$false; $backendStatus='not reachable yet'; $frontendStatus='not reachable yet'; $nextStatus=Get-Date; $handler=[ConsoleCancelEventHandler]{ param($sender,$e) $e.Cancel=$true; $script:shutdown=$true; Write-Host ''; Write-Host '[INFO] CTRL+C received. Stopping backend and frontend...' }; [Console]::add_CancelKeyPress($handler); function StopP([System.Diagnostics.Process]$p){ if($p -and -not $p.HasExited){ try{ taskkill /PID $p.Id /T /F | Out-Null } catch{} } }; try { if($env:DOCTALK_NEED_FRONTEND_INSTALL -eq '1'){ Write-Host '[INFO] Installing frontend dependencies...'; $install=Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d','/s','/c',$env:DOCTALK_FRONTEND_INSTALL_CMD) -WorkingDirectory $env:DOCTALK_FRONTEND_DIR -Wait -PassThru; if($install.ExitCode -ne 0){ throw 'Frontend install failed.' } }; $backend=Start-Process -FilePath $env:DOCTALK_BACKEND_EXE -ArgumentList @('-m','uvicorn','backend.main:app','--reload','--reload-dir','backend','--host','127.0.0.1','--port',$env:DOCTALK_BACKEND_PORT) -WorkingDirectory $root -PassThru -NoNewWindow; $frontendCommand=$env:DOCTALK_FRONTEND_DEV_CMD + ' -- --host 127.0.0.1 --port ' + $env:DOCTALK_FRONTEND_PORT + ' --strictPort'; $frontend=Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d','/s','/c',$frontendCommand) -WorkingDirectory $env:DOCTALK_FRONTEND_DIR -PassThru -NoNewWindow; Write-Host '[INFO] [4/5] Waiting for service readiness'; $deadline=(Get-Date).AddSeconds(45); while(-not $shutdown -and (-not $backendReady -or -not $frontendReady)){ if(-not $backendReady){ try{ Invoke-WebRequest -UseBasicParsing ('http://127.0.0.1:' + $env:DOCTALK_BACKEND_PORT + '/health') -TimeoutSec 2 | Out-Null; $backendReady=$true; $backendStatus='ready'; Write-Host '[OK] Backend health endpoint is reachable' }catch{} }; if(-not $frontendReady){ try{ Invoke-WebRequest -UseBasicParsing ('http://127.0.0.1:' + $env:DOCTALK_FRONTEND_PORT) -TimeoutSec 2 | Out-Null; $frontendReady=$true; $frontendStatus='ready'; Write-Host '[OK] Frontend dev server is reachable' }catch{} }; if((Get-Date) -ge $nextStatus){ Write-Host ('[STATUS] backend={0} frontend={1} supabase=external (postgresql)' -f $backendStatus, $frontendStatus); $nextStatus=(Get-Date).AddSeconds(15) }; if((Get-Date) -ge $deadline -and (-not $backendReady -or -not $frontendReady)){ if(-not $backendReady){ Write-Host '[WARN] Backend health endpoint is not reachable yet.' }; if(-not $frontendReady){ Write-Host '[WARN] Frontend dev server is not reachable yet.' }; break }; Start-Sleep -Seconds 1 }; Write-Host ''; Write-Host '=============================================================='; Write-Host '  Startup Summary'; Write-Host '=============================================================='; Write-Host ('Backend:  http://127.0.0.1:{0}   [{1}]' -f $env:DOCTALK_BACKEND_PORT, $backendStatus); Write-Host ('API docs: http://127.0.0.1:{0}/docs' -f $env:DOCTALK_BACKEND_PORT); Write-Host ('Frontend: http://127.0.0.1:{0}   [{1}]' -f $env:DOCTALK_FRONTEND_PORT, $frontendStatus); Write-Host 'Database: Supabase PostgreSQL (external)'; Write-Host ''; Write-Host 'Terminals started: Backend, Frontend'; Write-Host ''; Write-Host '[INFO] Development orchestrator is running. Press Ctrl+C to stop all services.'; while(-not $shutdown){ if((Get-Date) -ge $nextStatus){ $backendStatus=if($backend -and $backend.HasExited){ 'stopped' } else { 'running' }; $frontendStatus=if($frontend -and $frontend.HasExited){ 'stopped' } else { 'running' }; Write-Host ('[STATUS] backend={0} frontend={1} supabase=external' -f $backendStatus, $frontendStatus); $nextStatus=(Get-Date).AddSeconds(15) }; if(($backend -and $backend.HasExited) -or ($frontend -and $frontend.HasExited)){ if($backend -and $backend.HasExited){ Write-Host ('[WARN] Backend exited with code ' + $backend.ExitCode + '.') }; if($frontend -and $frontend.HasExited){ Write-Host ('[WARN] Frontend exited with code ' + $frontend.ExitCode + '.') }; break }; Start-Sleep -Seconds 1 } } finally { $shutdown=$true; StopP $frontend; StopP $backend; [Console]::remove_CancelKeyPress($handler) }"
exit /b %errorlevel%