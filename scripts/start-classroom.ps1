param(
    [int]$BackendPort = 5001,
    [int]$FrontendPort = 5188,
    [string]$PythonPath = '',
    [string]$DemoAccount = 'demo',
    [string]$DemoPassword = 'link123',
    [string]$DatabaseUrl = '',
    [string]$RuntimeDataDirectory = '',
    [switch]$RequireEnv
)

$ErrorActionPreference = 'Stop'
$projectPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$backendPath = Join-Path $projectPath 'backend'
$frontendPath = Join-Path $projectPath 'frontend'
$backendUrl = "http://127.0.0.1:$BackendPort"
$frontendUrl = "http://127.0.0.1:$FrontendPort"
$envFile = Join-Path $backendPath '.env'

function Resolve-Executable([string]$path, [string]$commandName) {
    if ($path) {
        if (-not (Test-Path -LiteralPath $path)) { throw "Cannot find ${commandName}: $path" }
        return (Resolve-Path -LiteralPath $path).Path
    }
    return (Get-Command $commandName -ErrorAction Stop).Source
}

function Wait-Http([string]$url, [string]$label, [int]$timeoutSeconds = 30) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
                return $response
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    } while ((Get-Date) -lt $deadline)
    throw "$label health check failed: $url"
}

$python = Resolve-Executable $PythonPath 'python.exe'
$node = Resolve-Executable '' 'node.exe'
$vite = Join-Path $frontendPath 'node_modules/vite/bin/vite.js'
if (-not (Test-Path -LiteralPath $vite)) { throw 'Missing frontend/node_modules/vite; run npm ci in frontend first.' }

& $python -c 'import flask, flask_jwt_extended, sqlalchemy' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Python dependency preflight failed: Flask/JWT/SQLAlchemy import failed.' }

$runtimeDirectory = if ($RuntimeDataDirectory) {
    if ([IO.Path]::IsPathRooted($RuntimeDataDirectory)) {
        [IO.Path]::GetFullPath($RuntimeDataDirectory)
    } else {
        [IO.Path]::GetFullPath((Join-Path $projectPath $RuntimeDataDirectory))
    }
} else {
    Join-Path $backendPath 'instance'
}
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null

$hasExplicitDatabase = $DatabaseUrl -or $env:DATABASE_URL
$hasEnvFile = Test-Path -LiteralPath $envFile
if ($RequireEnv -and -not $hasEnvFile -and -not $hasExplicitDatabase) {
    throw 'Missing backend/.env; configure it using docs/classroom-runbook.md, or pass -DatabaseUrl for an isolated run.'
}

$localFallback = $false
if ($DatabaseUrl) {
    $env:DATABASE_URL = $DatabaseUrl
    Write-Output "Using explicit database URL override: $DatabaseUrl"
} elseif (-not $hasEnvFile -and -not $env:DATABASE_URL) {
    $databasePath = Join-Path $runtimeDirectory 'classroom-local.db'
    $env:DATABASE_URL = "sqlite:///$($databasePath -replace '\\', '/')"
    $env:SEED_ON_STARTUP = 'true'
    if (-not $env:JWT_SECRET_KEY) {
        $env:JWT_SECRET_KEY = 'local-classroom-smoke-test-secret-20260910'
    }
    $localFallback = $true
    Write-Warning "backend/.env is missing; using local SQLite fallback for loopback smoke testing only: $databasePath"
}

if ($localFallback) {
    Write-Output 'Startup configuration: local SQLite fallback (smoke test only).'
} elseif ($hasEnvFile) {
    Write-Output 'Startup configuration: backend/.env.'
} else {
    Write-Output 'Startup configuration: process environment.'
}

$suffix = Get-Date -Format 'yyyyMMdd-HHmmss'
$backendPortInUse = Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue
if ($backendPortInUse) {
    $null = Wait-Http "$backendUrl/api/health" 'Existing backend'
    Write-Output "Backend already healthy, port=$BackendPort"
} else {
    $entry = Join-Path $PSScriptRoot 'run_classroom_backend.py'
    $process = Start-Process -FilePath $python -ArgumentList @($entry, '--port', "$BackendPort") -WorkingDirectory $backendPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDirectory "$suffix-backend.stdout.log") -RedirectStandardError (Join-Path $runtimeDirectory "$suffix-backend.stderr.log")
    $null = Wait-Http "$backendUrl/api/health" 'Backend startup'
    Write-Output "Backend healthy, PID=$($process.Id), $backendUrl"
}

$loginBody = @{ account = $DemoAccount; password = $DemoPassword; role = 'student' } | ConvertTo-Json
try {
    $login = Invoke-RestMethod -Method Post -Uri "$backendUrl/api/auth/login" -ContentType 'application/json' -Body $loginBody -TimeoutSec 5
    if (-not $login.access_token) { throw 'Response has no access_token' }
} catch {
    throw "Demo account preflight failed for ${DemoAccount}: $($_.Exception.Message)"
}
Write-Output "Demo account preflight passed: $DemoAccount"

$frontendPortInUse = Get-NetTCPConnection -LocalPort $FrontendPort -State Listen -ErrorAction SilentlyContinue
if ($frontendPortInUse) {
    $null = Wait-Http $frontendUrl 'Existing frontend'
    Write-Output "Frontend already healthy, port=$FrontendPort"
} else {
    $env:LINK_BACKEND_URL = $backendUrl
    $process = Start-Process -FilePath $node -ArgumentList @($vite, '--host', '127.0.0.1', '--port', "$FrontendPort") -WorkingDirectory $frontendPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDirectory "$suffix-frontend.stdout.log") -RedirectStandardError (Join-Path $runtimeDirectory "$suffix-frontend.stderr.log")
    $null = Wait-Http $frontendUrl 'Frontend startup'
    Write-Output "Frontend healthy, PID=$($process.Id), $frontendUrl/classroom"
}

Write-Output 'Startup preflight passed: dependencies, ports, backend health, demo login, and frontend health.'
