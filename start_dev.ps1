param()

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $RepoRoot

Write-Host "[DocTalk] Root path: $RepoRoot"

if (-not (Test-Path "$RepoRoot\.venv\Scripts\python.exe")) {
    Write-Host "[DocTalk] Creating Python virtual environment..."
    python -m venv "$RepoRoot\.venv"
}

if (-not (Test-Path "$RepoRoot\.venv\Scripts\python.exe")) {
    Write-Error "Python virtual environment could not be created. Ensure Python is installed and available on PATH."
    exit 1
}

Write-Host "[DocTalk] Installing backend Python dependencies..."
& "$RepoRoot\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "$RepoRoot\.venv\Scripts\python.exe" -m pip install -r "$RepoRoot\backend\requirements.txt"

if (-not (Test-Path "$RepoRoot\frontend\node_modules")) {
    Write-Host "[DocTalk] Installing frontend npm dependencies..."
    Push-Location "$RepoRoot\frontend"
    npm install
    Pop-Location
}

Write-Host "[DocTalk] Generating Prisma client..."
& "$RepoRoot\.venv\Scripts\python.exe" -m prisma generate --schema="$RepoRoot\backend\prisma\schema.prisma"

$backendCommand = "Set-Location -LiteralPath '$RepoRoot\backend'; . '$RepoRoot\.venv\Scripts\Activate.ps1'; uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000"
$frontendCommand = "Set-Location -LiteralPath '$RepoRoot\frontend'; npm run dev"

Write-Host "[DocTalk] Starting backend window..."
Start-Process powershell -ArgumentList @('-NoExit','-ExecutionPolicy','Bypass','-Command',$backendCommand)

Write-Host "[DocTalk] Starting frontend window..."
Start-Process powershell -ArgumentList @('-NoExit','-ExecutionPolicy','Bypass','-Command',$frontendCommand)

Write-Host "[DocTalk] Dev environment launched. Backend on http://127.0.0.1:8000 and frontend on Vite default port."
