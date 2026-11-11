param(
    [int]$Port = $(if ($env:PORT -and ($env:PORT -match '^\d+$')) { [int]$env:PORT } else { 8100 }),
    [switch]$Rebuild,
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $Root
$CommonPath = Join-Path $RepoRoot "scripts\common.ps1"
if (Test-Path $CommonPath) {
    . $CommonPath
}

try { $Host.UI.RawUI.WindowTitle = "IMACASA PC10 - UI Web ($Port)" } catch {}

function Get-NewestWriteTime {
    param([string[]]$Paths)
    $latest = [datetime]::MinValue
    foreach ($p in $Paths) {
        if (-not (Test-Path $p)) { continue }
        $item = Get-Item $p -ErrorAction SilentlyContinue
        if (-not $item) { continue }
        if ($item.PSIsContainer) {
            $child = Get-ChildItem -Path $p -Recurse -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            if ($child -and $child.LastWriteTime -gt $latest) {
                $latest = $child.LastWriteTime
            }
        } elseif ($item.LastWriteTime -gt $latest) {
            $latest = $item.LastWriteTime
        }
    }
    return $latest
}

$FrontendDir = Join-Path $Root "frontend"
$BackendDir = Join-Path $Root "backend"

# Check if port is already occupied before building/starting
$portBusy = $false
if (Get-Command Test-TcpPort -ErrorAction SilentlyContinue) {
    $portBusy = Test-TcpPort -Port $Port
}
if ($portBusy) {
    $check = Invoke-HttpCheck -Url "http://127.0.0.1:$Port/" -TimeoutSec 2
    if ($check.StatusCode -eq 200) {
        Write-Host "[OK] La aplicacion UI ya esta corriendo en http://127.0.0.1:$Port" -ForegroundColor Green
        if ($OpenBrowser) {
            Start-Process "http://127.0.0.1:$Port" | Out-Null
        }
        exit 0
    }
    throw "El puerto $Port ya esta en uso por otro proceso. Libera el puerto o usa -Port <otro>."
}

# 1) Frontend dependencies
$ModulesMarker = Join-Path $FrontendDir "node_modules\.modules.yaml"
$LockFile = Join-Path $FrontendDir "pnpm-lock.yaml"
$NeedInstall = $Rebuild -or (-not (Test-Path $ModulesMarker)) -or ((Test-Path $LockFile) -and ((Get-Item $LockFile).LastWriteTime -gt (Get-Item $ModulesMarker).LastWriteTime))

if ($NeedInstall) {
    Write-Host "==> Instalando dependencias del frontend (pnpm)..." -ForegroundColor Cyan
    Push-Location $FrontendDir
    try {
        $code = Invoke-LiveNative { pnpm install --frozen-lockfile }
        if ($code -ne 0) { exit $code }
    } finally {
        Pop-Location
    }
}

# 2) Frontend build
$DistIndex = Join-Path $FrontendDir "dist\index.html"
$FrontendInputs = @(
    (Join-Path $FrontendDir "src"),
    (Join-Path $FrontendDir "public"),
    (Join-Path $FrontendDir "index.html"),
    (Join-Path $FrontendDir "package.json"),
    (Join-Path $FrontendDir "vite.config.ts"),
    (Join-Path $FrontendDir "tsconfig.json"),
    (Join-Path $FrontendDir "tsconfig.app.json")
)
$NeedBuild = $Rebuild -or (-not (Test-Path $DistIndex))
if (-not $NeedBuild) {
    $latestSrc = Get-NewestWriteTime -Paths $FrontendInputs
    if ($latestSrc -gt (Get-Item $DistIndex).LastWriteTime) {
        $NeedBuild = $true
    }
}

if ($NeedBuild) {
    Write-Host "==> Compilando frontend (pnpm build)..." -ForegroundColor Cyan
    Push-Location $FrontendDir
    try {
        $code = Invoke-LiveNative { pnpm build }
        if ($code -ne 0) { exit $code }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "[OK] Frontend compilado al dia (usa -Rebuild para recompilar)." -ForegroundColor Green
}

# 3) Backend venv
$VenvCfg = Join-Path $BackendDir ".venv\pyvenv.cfg"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$BackendLock = Join-Path $BackendDir "uv.lock"
$BackendPyproject = Join-Path $BackendDir "pyproject.toml"
$NeedSync = $Rebuild -or (-not (Test-Path $VenvCfg)) -or (-not (Test-Path $VenvPython))
if (-not $NeedSync) {
    $latestBackend = Get-NewestWriteTime -Paths @($BackendLock, $BackendPyproject)
    if ($latestBackend -gt (Get-Item $VenvCfg).LastWriteTime) {
        $NeedSync = $true
    }
}

if ($NeedSync) {
    Write-Host "==> Sincronizando entorno backend (uv sync)..." -ForegroundColor Cyan
    Push-Location $BackendDir
    try {
        $code = Invoke-LiveNative { uv sync }
        if ($code -ne 0) { exit $code }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "[OK] Entorno backend listo." -ForegroundColor Green
}

if ($OpenBrowser) {
    $openScript = "for (`$i = 0; `$i -lt 60; `$i++) { try { if ((Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:$Port/' -TimeoutSec 2).StatusCode -eq 200) { Start-Process 'http://127.0.0.1:$Port'; break } } catch {}; Start-Sleep -Milliseconds 500 }"
    $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($openScript))
    Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -ArgumentList "-NoProfile -EncodedCommand $encoded" | Out-Null
}

Write-Host ""
Write-Host "==> Iniciando aplicacion UI en http://127.0.0.1:$Port" -ForegroundColor Cyan
Write-Host "    Usuarios demo: yo / yo  |  admin / Planta-Admin-2026  |  operador / Planta-Operador-2026" -ForegroundColor Gray
Write-Host "    Presiona Ctrl+C para detener la aplicacion." -ForegroundColor Gray
Write-Host ""

Set-Location $BackendDir
$ErrorActionPreference = "Continue"
if (Test-Path $VenvPython) {
    & $VenvPython -m uvicorn app.main:app --host 127.0.0.1 --port $Port
} else {
    & uv run uvicorn app.main:app --host 127.0.0.1 --port $Port
}
exit $LASTEXITCODE
