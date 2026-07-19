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

# Check and install backend dependencies if needed
$backendReqs = "$RepoRoot\backend\requirements.txt"
$backendFlag = "$RepoRoot\.venv\.installed_reqs"
$installBackend = $true

if (Test-Path $backendFlag) {
    $reqTime = (Get-Item $backendReqs).LastWriteTime
    $flagTime = (Get-Item $backendFlag).LastWriteTime
    if ($reqTime -le $flagTime) {
        $installBackend = $false
    }
}

if ($installBackend) {
    Write-Host "[DocTalk] Installing backend Python dependencies..."
    & "$RepoRoot\.venv\Scripts\python.exe" -m pip install --upgrade pip
    & "$RepoRoot\.venv\Scripts\python.exe" -m pip install -r $backendReqs
    
    if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq $null) {
        New-Item -ItemType File -Path $backendFlag -Force | Out-Null
    }
} else {
    Write-Host "[DocTalk] Backend Python dependencies are up to date."
}

# Check frontend dependencies
if (-not (Test-Path "$RepoRoot\frontend\node_modules")) {
    Write-Host "[DocTalk] Installing frontend npm dependencies..."
    Push-Location "$RepoRoot\frontend"
    npm install
    Pop-Location
} else {
    Write-Host "[DocTalk] Frontend npm dependencies are already installed."
}

# Check root dependencies (for concurrently)
if (-not (Test-Path "$RepoRoot\node_modules")) {
    Write-Host "[DocTalk] Installing root npm dependencies..."
    npm install
}

Write-Host "[DocTalk] Generating Prisma client..."
& "$RepoRoot\.venv\Scripts\python.exe" -m prisma generate --schema="$RepoRoot\backend\prisma\schema.prisma"

$backendCommand = "`"$RepoRoot\.venv\Scripts\python.exe`" -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000"
$frontendCommand = "npm run dev --prefix `"$RepoRoot\frontend`""

Write-Host "[DocTalk] Starting development servers..."
Write-Host "Press Ctrl+C to stop all servers."

npx concurrently --kill-others --names "BACKEND,FRONTEND" -c "blue,green" $backendCommand $frontendCommand
