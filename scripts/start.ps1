$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$venvDir = Join-Path $backendDir ".venv313"
$venvPython = Join-Path $venvDir "Scripts\\python.exe"
$requirementsFile = Join-Path $backendDir "requirements.txt"
$pipCacheDir = Join-Path $backendDir ".pip-cache"
$tempDir = Join-Path $repoRoot ".tmp"
$frontendIndex = Join-Path $repoRoot "frontend\\dist\\index.html"
$frontendSourceDir = Join-Path $repoRoot "frontend\\src"
$frontendStyles = Join-Path $repoRoot "frontend\\styles.css"
$frontendHtml = Join-Path $repoRoot "frontend\\index.html"
$hostAddress = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$port = if ($env:PORT) { $env:PORT } else { "8000" }

if (-not (Test-Path $tempDir)) {
    New-Item -ItemType Directory -Path $tempDir | Out-Null
}

$env:TEMP = $tempDir
$env:TMP = $tempDir

if (-not (Test-Path $venvPython)) {
    try {
        python -m venv $venvDir
    }
    catch {
        if (-not (Test-Path $venvPython)) {
            throw
        }
    }
}

$depsReady = $true
try {
    & $venvPython -c "import fastapi, sqlalchemy, uvicorn" | Out-Null
}
catch {
    $depsReady = $false
}

if (-not $depsReady) {
    python -m pip --python $venvPython install --cache-dir $pipCacheDir -r $requirementsFile --progress-bar off
}

function Get-LatestWriteTime([string[]]$paths) {
    $latest = $null
    foreach ($path in $paths) {
        if (-not (Test-Path $path)) {
            continue
        }
        $items = if ((Get-Item $path).PSIsContainer) {
            Get-ChildItem -Path $path -Recurse -File
        }
        else {
            Get-Item $path
        }
        foreach ($item in $items) {
            if (-not $latest -or $item.LastWriteTimeUtc -gt $latest) {
                $latest = $item.LastWriteTimeUtc
            }
        }
    }
    return $latest
}

$frontendSourceTimestamp = Get-LatestWriteTime @($frontendSourceDir, $frontendStyles, $frontendHtml)
$frontendDistTimestamp = Get-LatestWriteTime @((Join-Path $repoRoot "frontend\\dist"))
$frontendNeedsBuild = (-not (Test-Path $frontendIndex)) -or (-not $frontendDistTimestamp) -or ($frontendSourceTimestamp -and $frontendSourceTimestamp -gt $frontendDistTimestamp)

if ($frontendNeedsBuild) {
    Push-Location $repoRoot
    try {
        cmd /c npm run build
    }
    finally {
        Pop-Location
    }
}

Push-Location $backendDir
try {
    $portNumber = [int]$port
    $existingListener = Get-NetTCPConnection -LocalPort $portNumber -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existingListener) {
        $existingProcess = Get-Process -Id $existingListener.OwningProcess -ErrorAction SilentlyContinue
        $processLabel = if ($existingProcess) {
            "$($existingProcess.ProcessName) (PID $($existingProcess.Id))"
        }
        else {
            "PID $($existingListener.OwningProcess)"
        }
        throw "Port $port is already in use by $processLabel. Stop that process or run with a different PORT."
    }

    & $venvPython create_database.py
    Write-Host "Open http://localhost:$port or http://127.0.0.1:$port in your browser."
    & $venvPython -m uvicorn app.main:app --host $hostAddress --port $port
}
finally {
    Pop-Location
}
