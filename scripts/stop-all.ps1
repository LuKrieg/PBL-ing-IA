param(
    [int]$UiPort = 8100,
    [int]$MockPort = 8000
)

$ErrorActionPreference = "Continue"
$ScriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptsDir
. (Join-Path $ScriptsDir "common.ps1")

try { $Host.UI.RawUI.WindowTitle = "IMACASA PC10 - Deteniendo servicios" } catch {}

function Stop-ProcessTreeOrSingle {
    param([int]$ProcessId, [string]$Label)
    if ($ProcessId -le 0 -or $ProcessId -eq $PID) { return }
    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
        Write-Ok "Detenido $Label (PID $ProcessId)"
    } catch {}
}

Write-Step "Deteniendo tunel (ngrok / cloudflared)..."
$stoppedTunnel = $false
try {
    $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        ($_.Name -in @("ngrok.exe", "cloudflared.exe") -and ($_.CommandLine -match "\b$MockPort\b" -or -not $_.CommandLine)) -or
        ($_.Name -eq "powershell.exe" -and $_.CommandLine -match "run-tunnel\.ps1")
    }
    foreach ($p in $procs) {
        Stop-ProcessTreeOrSingle -ProcessId ([int]$p.ProcessId) -Label $p.Name
        $stoppedTunnel = $true
    }
} catch {}

if (-not $stoppedTunnel) {
    foreach ($name in @("ngrok", "cloudflared")) {
        foreach ($proc in (Get-Process -Name $name -ErrorAction SilentlyContinue)) {
            Stop-ProcessTreeOrSingle -ProcessId $proc.Id -Label $proc.ProcessName
            $stoppedTunnel = $true
        }
    }
}
if (-not $stoppedTunnel) {
    Write-Host "  (No habia procesos de tunel activos)" -ForegroundColor Gray
}

Write-Step "Deteniendo aplicacion UI (puerto $UiPort)..."
$stoppedUi = $false
$uiPids = Get-ListeningPids -Port $UiPort
foreach ($upid in $uiPids) {
    try {
        $procInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $upid" -ErrorAction SilentlyContinue
        Stop-ProcessTreeOrSingle -ProcessId $upid -Label "UI backend"
        $stoppedUi = $true
        if ($procInfo -and $procInfo.ParentProcessId) {
            $parentInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $($procInfo.ParentProcessId)" -ErrorAction SilentlyContinue
            if ($parentInfo -and $parentInfo.Name -in @("uv.exe", "powershell.exe") -and ($parentInfo.CommandLine -match "01-ui|run\.ps1|uvicorn")) {
                Stop-ProcessTreeOrSingle -ProcessId ([int]$parentInfo.ProcessId) -Label $parentInfo.Name
            }
        }
    } catch {}
}

try {
    $uiWindows = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -eq "powershell.exe" -and $_.CommandLine -match "01-ui[\\/]+run\.ps1" -and $_.ProcessId -ne $PID
    }
    foreach ($w in $uiWindows) {
        Stop-ProcessTreeOrSingle -ProcessId ([int]$w.ProcessId) -Label "Ventana UI"
        $stoppedUi = $true
    }
} catch {}
if (-not $stoppedUi) {
    Write-Host "  (La aplicacion UI no estaba corriendo en el puerto $UiPort)" -ForegroundColor Gray
}

Write-Step "Deteniendo contenedor Docker (05-mock-service)..."
$mockDir = Join-Path $RepoRoot "05-mock-service"
if (Get-Command docker -ErrorAction SilentlyContinue) {
    $infoRes = Invoke-QuietNative { docker info }
    if ($infoRes.ExitCode -eq 0) {
        Push-Location $mockDir
        try {
            $downCode = Invoke-LiveNative { docker compose down }
            if ($downCode -eq 0) {
                Write-Ok "Contenedor Docker detenido."
            }
        } finally {
            Pop-Location
        }
    } else {
        Write-WarnMsg "Docker no esta corriendo; se omite 'docker compose down'."
    }
} else {
    Write-WarnMsg "No se encontro 'docker' en PATH."
}

Write-Host ""
Write-Ok "Limpieza completada."
