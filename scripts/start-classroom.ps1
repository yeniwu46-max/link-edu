param([int]$BackendPort=5001,[int]$FrontendPort=5188,[string]$PythonPath='')
$ErrorActionPreference='Stop'
$projectPath=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$backendPath=Join-Path $projectPath 'backend'
$frontendPath=Join-Path $projectPath 'frontend'
if (-not (Test-Path -LiteralPath (Join-Path $backendPath '.env'))) { throw 'Configure backend/.env first; see docs/classroom-runbook.md' }
if (-not $PythonPath) {
    if (Test-Path -LiteralPath 'C:\Python314\python.exe') { $PythonPath='C:\Python314\python.exe' }
    else { $PythonPath=(Get-Command python.exe).Source }
}
$nodePath=(Get-Command node.exe).Source
$logPath=Join-Path $backendPath 'instance'
New-Item -ItemType Directory -Path $logPath -Force | Out-Null
$suffix=Get-Date -Format 'yyyyMMdd-HHmmss'
if (Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue) {
    Write-Warning "Port $BackendPort is occupied. Existing process was not stopped or assumed up to date."
} else {
    $entry=Join-Path $PSScriptRoot 'run_classroom_backend.py'
    $process=Start-Process -FilePath $PythonPath -ArgumentList @('"'+$entry+'"','--port',$BackendPort) -WorkingDirectory $backendPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logPath "$suffix-backend.stdout.log") -RedirectStandardError (Join-Path $logPath "$suffix-backend.stderr.log")
    Write-Output "Backend launched, PID=$($process.Id), http://127.0.0.1:$BackendPort"
}
if (Get-NetTCPConnection -LocalPort $FrontendPort -State Listen -ErrorAction SilentlyContinue) {
    Write-Warning "Port $FrontendPort is occupied. Check its Vite proxy points to port $BackendPort."
} else {
    $vite=Join-Path $frontendPath 'node_modules/vite/bin/vite.js'
    if (-not (Test-Path -LiteralPath $vite)) { throw 'Run npm ci in frontend first' }
    $env:LINK_BACKEND_URL="http://127.0.0.1:$BackendPort"
    $process=Start-Process -FilePath $nodePath -ArgumentList @('"'+$vite+'"','--host','127.0.0.1','--port',$FrontendPort) -WorkingDirectory $frontendPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logPath "$suffix-frontend.stdout.log") -RedirectStandardError (Join-Path $logPath "$suffix-frontend.stderr.log")
    Write-Output "Frontend launched, PID=$($process.Id), http://127.0.0.1:$FrontendPort/classroom"
}
Write-Output 'Launch is not verification. Log in and run the four capability checks before rehearsal.'
