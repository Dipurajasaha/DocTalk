@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

rem ------------------------------------------------------------
rem DocTalk local development starter
rem Usage:
rem   start_dev.bat
rem   start_dev.bat --logs      (opens docker logs terminal)
rem   start_dev.bat --check     (validation only, no terminals)
rem Environment toggles:
rem   DOCTALK_PRISMA_SYNC=1     (bypassed/no-op in mysql mode)
rem ------------------------------------------------------------

call :init_colors
call :banner

set "OPEN_LOGS=0"
set "CHECK_ONLY=0"
for %%A in (%*) do (
    if /I "%%~A"=="--logs" set "OPEN_LOGS=1"
    if /I "%%~A"=="--check" set "CHECK_ONLY=1"
)

set "ROOT=%CD%"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"

call :info "[1/6] Infrastructure checks"

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

if not exist "docker-compose.yml" (
    call :err "Missing docker-compose.yml. Cannot start MySQL service."
    exit /b 1
)

call :detect_frontend_pm
if errorlevel 1 exit /b 1

call :pick_frontend_port
if errorlevel 1 exit /b 1

if not exist "frontend\node_modules" (
    set "NEED_FRONTEND_INSTALL=1"
    call :warn "frontend\node_modules is missing. The frontend terminal will run install first."
) else (
    set "NEED_FRONTEND_INSTALL=0"
    call :ok "Frontend dependencies directory exists"
)

docker --version >nul 2>&1
if errorlevel 1 (
    call :err "Docker CLI not found. Install Docker Desktop and retry."
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    call :err "Docker daemon is not reachable. Start Docker Desktop and retry."
    exit /b 1
)
call :ok "Docker CLI and daemon are available"

call :info "[2/6] Starting MySQL via Docker Compose"
docker compose up -d mysql >nul 2>&1
if errorlevel 1 (
    call :err "Failed to start mysql service with docker compose."
    exit /b 1
)

call :wait_mysql 60
if errorlevel 1 (
    call :err "MySQL did not become healthy in time."
    exit /b 1
)
call :ok "MySQL is healthy"

call :info "[3/6] Checking Gemini API configuration"
set "GEMINI_READY=0"
if not exist ".env" (
    call :warn "Missing .env. Copy .env.example and set GEMINI_API_KEY for AI features."
) else (
    findstr /I /B "GEMINI_API_KEY=" ".env" | findstr /V /I "your_gemini_api_key_here" >nul 2>&1
    if errorlevel 1 (
        call :warn "GEMINI_API_KEY is missing or still a placeholder. AI chat, vision, and RAG embeddings will fall back or fail."
    ) else (
        set "GEMINI_READY=1"
        call :ok "GEMINI_API_KEY is configured"
    )
)

call :info "[4/6] Database schema checks"
call :ok "Schema checks bypassed (schema auto-initializes on startup)"

if "%CHECK_ONLY%"=="1" (
    call :info "Check-only mode complete. No terminals were started."
    exit /b 0
)

call :info "[5/6] Starting backend and frontend under the orchestrator"

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
set "DOCTALK_LAUNCH_STREAMLIT=0"
set "DOCTALK_STREAMLIT_PORT=8501"
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
echo   DocTalk Local Development Starter
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

:wait_mysql
set /a "MAX_TRIES=%~1"
if "%MAX_TRIES%"=="" set "MAX_TRIES=60"
for /L %%I in (1,1,%MAX_TRIES%) do (
    for /f "usebackq delims=" %%S in (`docker inspect -f "{{.State.Health.Status}}" doctalk-mysql 2^>nul`) do set "PG_STATUS=%%S"
    if /I "!PG_STATUS!"=="healthy" exit /b 0
    ping -n 2 127.0.0.1 >nul
)
exit /b 1

:wait_ollama
set /a "MAX_TRIES=%~1"
if "%MAX_TRIES%"=="" set "MAX_TRIES=20"
for /L %%I in (1,1,%MAX_TRIES%) do (
    ollama list >nul 2>&1
    if not errorlevel 1 exit /b 0
    ping -n 2 127.0.0.1 >nul
)
exit /b 1

:check_ollama_models
for /f "skip=1 tokens=1" %%M in ('ollama list 2^>nul') do (
    if /I "%%M"=="qwen2.5:7b-instruct" set "MODEL_QWEN=1"
    if /I "%%M"=="nomic-embed-text" set "MODEL_EMBED=1"
    if /I "%%M"=="llama3.2-vision" set "MODEL_VISION=1"
)

if "%MODEL_QWEN%"=="0" call :warn "Missing Ollama model: qwen2.5:7b-instruct"
if "%MODEL_EMBED%"=="0" call :warn "Missing Ollama model: nomic-embed-text"
if "%MODEL_VISION%"=="0" call :warn "Missing Ollama model: llama3.2-vision"

if "%MODEL_QWEN%"=="1" if "%MODEL_EMBED%"=="1" if "%MODEL_VISION%"=="1" (
    call :ok "All required Ollama models are available"
) else (
    call :warn "Pull missing model(s) with: ollama pull <model_name>"
)
exit /b 0

:wait_http
set "WAIT_URL=%~1"
set /a "WAIT_TRIES=%~2"
if "%WAIT_TRIES%"=="" set "WAIT_TRIES=45"
for /L %%I in (1,1,%WAIT_TRIES%) do (
    curl -fsS "%WAIT_URL%" >nul 2>&1
    if not errorlevel 1 exit /b 0
    ping -n 2 127.0.0.1 >nul
)
exit /b 1

:summary
echo.
echo ==============================================================
echo   Startup Summary
echo ==============================================================
echo Backend:  http://127.0.0.1:%BACKEND_PORT%   [%BACKEND_STATUS%]
echo API docs: http://127.0.0.1:%BACKEND_PORT%/docs
echo Frontend: http://127.0.0.1:%FRONTEND_PORT%   [%FRONTEND_STATUS%]

docker inspect -f "{{.State.Health.Status}}" doctalk-mysql >nul 2>&1
if errorlevel 1 (
    echo Database: mysql container not detected
) else (
    for /f "usebackq delims=" %%S in (`docker inspect -f "{{.State.Health.Status}}" doctalk-mysql 2^>nul`) do set "PG_SUM=%%S"
    echo Database: mysql container health = !PG_SUM!
)

if "%GEMINI_READY%"=="1" (
    echo Gemini:   API key configured
) else (
    echo Gemini:   API key missing
)
echo.
set "TERMINALS=Backend, Frontend"
if "%OPEN_LOGS%"=="1" set "TERMINALS=Backend, Frontend, Logs"
echo Terminals started: %TERMINALS%
echo.
exit /b 0

:orchestrate
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $root=$env:DOCTALK_ROOT; $backend=$null; $frontend=$null; $streamlit=$null; $shutdown=$false; $backendReady=$false; $frontendReady=$false; $streamlitReady=$false; $backendStatus='not reachable yet'; $frontendStatus='not reachable yet'; $streamlitStatus='not reachable yet'; $nextStatus=Get-Date; $handler=[ConsoleCancelEventHandler]{ param($sender,$e) $e.Cancel=$true; $script:shutdown=$true; Write-Host ''; Write-Host '[INFO] CTRL+C received. Stopping backend and frontend...' }; [Console]::add_CancelKeyPress($handler); function StopP([System.Diagnostics.Process]$p){ if($p -and -not $p.HasExited){ try{ taskkill /PID $p.Id /T /F | Out-Null } catch{} } }; try { if($env:DOCTALK_NEED_FRONTEND_INSTALL -eq '1'){ Write-Host '[INFO] Installing frontend dependencies...'; $install=Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d','/s','/c',$env:DOCTALK_FRONTEND_INSTALL_CMD) -WorkingDirectory $env:DOCTALK_FRONTEND_DIR -Wait -PassThru; if($install.ExitCode -ne 0){ throw 'Frontend install failed.' } }; $backend=Start-Process -FilePath $env:DOCTALK_BACKEND_EXE -ArgumentList @('-m','uvicorn','backend.main:app','--reload','--reload-dir','backend','--host','127.0.0.1','--port',$env:DOCTALK_BACKEND_PORT) -WorkingDirectory $root -PassThru -NoNewWindow; $frontendCommand=$env:DOCTALK_FRONTEND_DEV_CMD + ' -- --host 127.0.0.1 --port ' + $env:DOCTALK_FRONTEND_PORT + ' --strictPort'; $frontend=Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d','/s','/c',$frontendCommand) -WorkingDirectory $env:DOCTALK_FRONTEND_DIR -PassThru -NoNewWindow; if($env:DOCTALK_LAUNCH_STREAMLIT -eq '1'){ $streamlitCmd='streamlit run "' + ($root + '\streamlit_app\app.py') + '" --server.port ' + $env:DOCTALK_STREAMLIT_PORT; $streamlit=Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d','/s','/c',$streamlitCmd) -WorkingDirectory $root -PassThru -NoNewWindow } Write-Host '[INFO] [6/6] Waiting for service readiness'; $deadline=(Get-Date).AddSeconds(45); while(-not $shutdown -and (-not $backendReady -or -not $frontendReady -or ($env:DOCTALK_LAUNCH_STREAMLIT -eq '1' -and -not $streamlitReady))){ if(-not $backendReady){ try{ Invoke-WebRequest -UseBasicParsing ('http://127.0.0.1:' + $env:DOCTALK_BACKEND_PORT + '/health') -TimeoutSec 2 | Out-Null; $backendReady=$true; $backendStatus='ready'; Write-Host '[OK] Backend health endpoint is reachable' }catch{} }; if(-not $frontendReady){ try{ Invoke-WebRequest -UseBasicParsing ('http://127.0.0.1:' + $env:DOCTALK_FRONTEND_PORT) -TimeoutSec 2 | Out-Null; $frontendReady=$true; $frontendStatus='ready'; Write-Host '[OK] Frontend dev server is reachable' }catch{} }; if($env:DOCTALK_LAUNCH_STREAMLIT -eq '1' -and -not $streamlitReady){ try{ Invoke-WebRequest -UseBasicParsing ('http://127.0.0.1:' + $env:DOCTALK_STREAMLIT_PORT) -TimeoutSec 2 | Out-Null; $streamlitReady=$true; $streamlitStatus='ready'; Write-Host '[OK] Streamlit dev server is reachable' }catch{} }; if((Get-Date) -ge $nextStatus){ $ollamaStatus=if($env:OLLAMA_READY -eq '1'){ 'reachable' } else { 'unavailable' }; Write-Host ('[STATUS] backend={0} frontend={1} streamlit={2} mysql=healthy ollama={3}' -f $backendStatus, $frontendStatus, $streamlitStatus, $ollamaStatus); $nextStatus=(Get-Date).AddSeconds(15) }; if((Get-Date) -ge $deadline -and (-not $backendReady -or -not $frontendReady -or ($env:DOCTALK_LAUNCH_STREAMLIT -eq '1' -and -not $streamlitReady))){ if(-not $backendReady){ Write-Host '[WARN] Backend health endpoint is not reachable yet.' }; if(-not $frontendReady){ Write-Host '[WARN] Frontend dev server is not reachable yet.' }; if($env:DOCTALK_LAUNCH_STREAMLIT -eq '1' -and -not $streamlitReady){ Write-Host '[WARN] Streamlit dev server is not reachable yet.' }; break }; Start-Sleep -Seconds 1 }; Write-Host ''; Write-Host '=============================================================='; Write-Host '  Startup Summary'; Write-Host '=============================================================='; Write-Host ('Backend:  http://127.0.0.1:{0}   [{1}]' -f $env:DOCTALK_BACKEND_PORT, $backendStatus); Write-Host ('API docs: http://127.0.0.1:{0}/docs' -f $env:DOCTALK_BACKEND_PORT); Write-Host ('Frontend: http://127.0.0.1:{0}   [{1}]' -f $env:DOCTALK_FRONTEND_PORT, $frontendStatus); Write-Host ('Streamlit: http://127.0.0.1:{0}   [{1}]' -f $env:DOCTALK_STREAMLIT_PORT, $streamlitStatus); Write-Host 'Database: mysql container health = healthy'; Write-Host ('Ollama:   {0}' -f $(if($env:OLLAMA_READY -eq '1'){ 'reachable' } else { 'unavailable' })); Write-Host ''; Write-Host 'Terminals started: Backend, Frontend'; Write-Host ''; Write-Host '[INFO] Development orchestrator is running. Press Ctrl+C to stop all services.'; while(-not $shutdown){ if((Get-Date) -ge $nextStatus){ $backendStatus=if($backend -and $backend.HasExited){ 'stopped' } else { 'running' }; $frontendStatus=if($frontend -and $frontend.HasExited){ 'stopped' } else { 'running' }; $streamlitStatus=if($streamlit -and $streamlit.HasExited){ 'stopped' } else { 'running' }; $ollamaStatus=if($env:OLLAMA_READY -eq '1'){ 'reachable' } else { 'unavailable' }; Write-Host ('[STATUS] backend={0} frontend={1} streamlit={2} mysql=healthy ollama={3}' -f $backendStatus, $frontendStatus, $streamlitStatus, $ollamaStatus); $nextStatus=(Get-Date).AddSeconds(15) }; if(($backend -and $backend.HasExited) -or ($frontend -and $frontend.HasExited) -or ($streamlit -and $streamlit.HasExited)){ if($backend -and $backend.HasExited){ Write-Host ('[WARN] Backend exited with code ' + $backend.ExitCode + '.') }; if($frontend -and $frontend.HasExited){ Write-Host ('[WARN] Frontend exited with code ' + $frontend.ExitCode + '.') }; if($streamlit -and $streamlit.HasExited){ Write-Host ('[WARN] Streamlit exited with code ' + $streamlit.ExitCode + '.') }; break }; Start-Sleep -Seconds 1 } } finally { $shutdown=$true; StopP $streamlit; StopP $frontend; StopP $backend; [Console]::remove_CancelKeyPress($handler) }"
exit /b %errorlevel%
