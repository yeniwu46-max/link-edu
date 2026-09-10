param(
    [string]$PythonPath = '',
    [string]$ReportPath = ''
)

$ErrorActionPreference = 'Stop'
$projectPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$frontendPath = Join-Path $projectPath 'frontend'

function Resolve-Executable([string]$path, [string]$commandName) {
    if ($path) {
        if (-not (Test-Path -LiteralPath $path)) { throw "Cannot find ${commandName}: $path" }
        return (Resolve-Path -LiteralPath $path).Path
    }
    return (Get-Command $commandName -ErrorAction Stop).Source
}

function Invoke-Check([string]$name, [string]$executable, [string[]]$arguments, [string]$workingDirectory) {
    $token = [Guid]::NewGuid().ToString('N')
    $stdoutPath = Join-Path ([IO.Path]::GetTempPath()) "link-regression-$token.stdout.log"
    $stderrPath = Join-Path ([IO.Path]::GetTempPath()) "link-regression-$token.stderr.log"
    try {
        $process = Start-Process -FilePath $executable -ArgumentList $arguments -WorkingDirectory $workingDirectory -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
        $stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -Raw -LiteralPath $stdoutPath } else { '' }
        $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -Raw -LiteralPath $stderrPath } else { '' }
        $output = (@($stdout, $stderr) -join "`n").Trim()
        $exitCode = $process.ExitCode
    } finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
    [pscustomobject]@{
        name = $name
        passed = ($exitCode -eq 0)
        exit_code = $exitCode
        output = $output
    }
}

$python = Resolve-Executable $PythonPath 'python.exe'
$npm = Resolve-Executable '' 'npm.cmd'
$checks = @(
    (Invoke-Check 'backend-tests' $python @('-m', 'pytest', 'backend/tests', '-q') $projectPath),
    (Invoke-Check 'frontend-tests' $npm @('test') $frontendPath),
    (Invoke-Check 'frontend-build' $npm @('run', 'build') $frontendPath)
)

$blockers = @($checks | Where-Object { -not $_.passed } | ForEach-Object {
    [pscustomobject]@{
        check = $_.name
        exit_code = $_.exit_code
        summary = (($_.output -split "`r?`n" | Select-Object -Last 12) -join "`n")
    }
})

if (-not $ReportPath) {
    $ReportPath = Join-Path $projectPath ('artifacts/regression-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
}
New-Item -ItemType Directory -Path (Split-Path -Parent $ReportPath) -Force | Out-Null
$report = [pscustomobject]@{
    generated_at = (Get-Date).ToString('o')
    project = $projectPath
    checks = $checks
    blockers = $blockers
    passed = ($blockers.Count -eq 0)
}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
$report | ConvertTo-Json -Depth 8

if ($blockers.Count -gt 0) {
    Write-Error "Regression blocked: $($blockers.Count) check(s) failed. Record: $ReportPath"
    exit 1
}
Write-Output "Regression passed. Record: $ReportPath"
