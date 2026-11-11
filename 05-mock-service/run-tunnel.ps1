param(
    [string]$Mode = "primary",
    [string]$Domain = $(if ($env:NGROK_DOMAIN) { $env:NGROK_DOMAIN } else { "diffusion-briskly-craftily.ngrok-free.dev" }),
    [int]$Port = 8000,
    [switch]$SkipTokenPrompt,
    [string]$LogFile = ""
)

$ErrorActionPreference = "Stop"
$MockDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $MockDir
. (Join-Path $RepoRoot "scripts\common.ps1")

$activeMode = if ($Mode -eq "backup") { "backup" } else { "primary" }
try { $Host.UI.RawUI.WindowTitle = "IMACASA PC10 - Tunel Publico ($activeMode -> $Port)" } catch {}

$health = Invoke-HttpCheck -Url "http://127.0.0.1:$Port/health" -TimeoutSec 2
if ($health.StatusCode -ne 200) {
    Write-WarnMsg "El mock service en http://127.0.0.1:$Port aun no responde /health (200)."
    Write-WarnMsg "El tunel puede iniciar igual, pero asegurate de levantar Docker con iniciar-mock-docker.bat."
}

function Invoke-CloudflaredTunnel {
    param([int]$TargetPort, [string]$OutLog)
    $cf = Find-ToolLocation -Name "cloudflared"
    if (-not $cf) {
        throw "No se encontro 'cloudflared' en Windows ni en WSL. Instalalo con: winget install --id Cloudflare.cloudflared -e"
    }
    try { $Host.UI.RawUI.WindowTitle = "IMACASA PC10 - Tunel Backup (cloudflared -> $TargetPort)" } catch {}
    Write-Step "Iniciando tunel de respaldo con cloudflared (URL aleatoria) hacia http://127.0.0.1:$TargetPort..."
    Write-Host "Presiona Ctrl+C para cerrar el tunel." -ForegroundColor Gray
    Write-Host ""
    if ($cf.Mode -eq "win") {
        if ($OutLog) {
            $cfCode = Invoke-LiveNative { & $cf.Path tunnel --url "http://127.0.0.1:$TargetPort" 2>&1 | Tee-Object -FilePath $OutLog }
        } else {
            $ErrorActionPreference = "Continue"
            & $cf.Path tunnel --url "http://127.0.0.1:$TargetPort"
            $cfCode = $LASTEXITCODE
        }
    } else {
        if ($OutLog) {
            $cfCode = Invoke-LiveNative { & wsl.exe -e cloudflared tunnel --url "http://localhost:$TargetPort" 2>&1 | Tee-Object -FilePath $OutLog }
        } else {
            $ErrorActionPreference = "Continue"
            & wsl.exe -e cloudflared tunnel --url "http://localhost:$TargetPort"
            $cfCode = $LASTEXITCODE
        }
    }
    exit $cfCode
}

if ($activeMode -eq "backup") {
    Invoke-CloudflaredTunnel -TargetPort $Port -OutLog $LogFile
}

$ng = Find-ToolLocation -Name "ngrok"
if (-not $ng) {
    Write-WarnMsg "No se encontro 'ngrok'. Buscando 'cloudflared' como respaldo..."
    Invoke-CloudflaredTunnel -TargetPort $Port -OutLog $LogFile
}

if (-not $SkipTokenPrompt -and -not (Test-NgrokAuthtokenConfigured -ToolMode $ng.Mode)) {
    Write-WarnMsg "No se detecto un authtoken configurado para ngrok."
    Write-Host "  1. Obten tu token gratis en: https://dashboard.ngrok.com/get-started/your-authtoken"
    Write-Host "  2. Pegalo abajo y presiona ENTER (se guarda una sola vez)."
    Write-Host "  3. O escribe 'backup' para usar cloudflared (sin cuenta)."
    Write-Host "  4. O presiona ENTER vacio para intentar iniciar ngrok de todos modos."
    $inputVal = (Read-Host "Authtoken / opcion").Trim()
    if ($inputVal -eq "backup") {
        Invoke-CloudflaredTunnel -TargetPort $Port -OutLog $LogFile
    } elseif ($inputVal) {
        $tokCode = if ($ng.Mode -eq "win") {
            Invoke-LiveNative { & $ng.Path config add-authtoken $inputVal }
        } else {
            Invoke-LiveNative { & wsl.exe -e ngrok config add-authtoken $inputVal }
        }
        if ($tokCode -ne 0) {
            throw "No se pudo guardar el authtoken de ngrok."
        }
        Write-Ok "Authtoken de ngrok guardado."
    }
}

Write-Step "Iniciando tunel ngrok hacia http://127.0.0.1:$Port"
Write-Host "  Dominio fijo: https://$Domain" -ForegroundColor Green
Write-Host "  Nota: un dominio gratuito de ngrok solo permite 1 tunel a la vez (deten nlp-qa-api si estaba usando este dominio)." -ForegroundColor Gray
Write-Host "  Presiona Ctrl+C para detener el tunel." -ForegroundColor Gray
Write-Host ""

$ErrorActionPreference = "Continue"
if ($ng.Mode -eq "win") {
    & $ng.Path http "--url=$Domain" "127.0.0.1:$Port"
} else {
    & wsl.exe -e ngrok http "--url=$Domain" "127.0.0.1:$Port"
}
$code = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($code -ne 0) {
    Write-Host ""
    Write-ErrMsg "ngrok termino con codigo $code."
    Write-Host "Causas frecuentes:" -ForegroundColor Yellow
    Write-Host "  - Falta configurar authtoken: ejecuta 'ngrok config add-authtoken <TU_TOKEN>'"
    Write-Host "  - El dominio '$Domain' esta ocupado por otro tunel (ej. nlp-qa-api)."
    Write-Host "  - Alternativa inmediata sin cuenta: ejecuta iniciar-tunel-backup.bat"
}
exit $code
