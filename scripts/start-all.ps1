param(
    [switch]$BackupTunnel,
    [switch]$NoBrowser,
    [switch]$RebuildUI
)

$ErrorActionPreference = "Stop"
$ScriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptsDir
. (Join-Path $ScriptsDir "common.ps1")

try { $Host.UI.RawUI.WindowTitle = "IMACASA PC10 - Lanzador Completo (Docker + UI + Tunel)" } catch {}

$MockDir = Join-Path $RepoRoot "05-mock-service"
$UiDir = Join-Path $RepoRoot "01-ui"
$MockPort = 8000
$UiPort = 8100
$Domain = if ($env:NGROK_DOMAIN) { $env:NGROK_DOMAIN } else { "diffusion-briskly-craftily.ngrok-free.dev" }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  IMACASA PC10 - Arranque de un clic (Docker + UI + Tunel)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# ------------------------------------------------------------------
# [1/3] Docker + Mock Service (05-mock-service)
# ------------------------------------------------------------------
Write-Host ""
Write-Host "[1/3] MOCK SERVICE EN DOCKER (puerto $MockPort)" -ForegroundColor White
$dockerScript = Join-Path $MockDir "run-docker.ps1"
& $dockerScript -Port $MockPort
if ($LASTEXITCODE -ne 0) {
    throw "Fallo la inicializacion del Mock Service en Docker."
}
$token = Read-EnvValue -EnvFile (Join-Path $MockDir ".env") -Key "INFO_TOKEN"

# ------------------------------------------------------------------
# [2/3] Aplicacion UI Web (01-ui)
# ------------------------------------------------------------------
Write-Host ""
Write-Host "[2/3] APLICACION WEB UI (puerto $UiPort)" -ForegroundColor White
$uiScript = Join-Path $UiDir "run.ps1"
$uiLocalUrl = "http://127.0.0.1:$UiPort"
$uiAlreadyUp = ((Invoke-HttpCheck -Url "$uiLocalUrl/" -TimeoutSec 2).StatusCode -eq 200)

if ($uiAlreadyUp -and -not $RebuildUI) {
    Write-Ok "La UI ya estaba corriendo en $uiLocalUrl"
} else {
    if ($uiAlreadyUp -and $RebuildUI) {
        Write-Step "Reiniciando UI para recompilar..."
        foreach ($upid in (Get-ListeningPids -Port $UiPort)) {
            Stop-Process -Id $upid -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 1
    } elseif (Test-TcpPort -Port $UiPort) {
        throw "El puerto $UiPort ya esta ocupado por otro proceso que no responde como la UI."
    }

    Write-Step "Abriendo ventana para la UI ($uiLocalUrl)..."
    $uiArgs = @("-Port", "$UiPort")
    if ($RebuildUI) { $uiArgs += "-Rebuild" }
    Start-PowerShellWindow -ScriptPath $uiScript -WorkingDirectory $UiDir -ScriptArgs $uiArgs | Out-Null

    Write-Step "Esperando a que la UI responda en $uiLocalUrl ..."
    if (-not (Wait-HttpReady -Url "$uiLocalUrl/" -TimeoutSeconds 90)) {
        throw "La UI no respondio en $uiLocalUrl dentro de 90s. Revisa la ventana 'IMACASA PC10 - UI Web ($UiPort)'."
    }
    Write-Ok "Aplicacion UI lista en $uiLocalUrl"
}

if (-not $NoBrowser) {
    Start-Process $uiLocalUrl | Out-Null
}

# ------------------------------------------------------------------
# [3/3] Tunel Publico (ngrok / cloudflared)
# ------------------------------------------------------------------
Write-Host ""
Write-Host "[3/3] TUNEL PUBLICO (hacia 127.0.0.1:$MockPort)" -ForegroundColor White
$tunnelScript = Join-Path $MockDir "run-tunnel.ps1"
$publicUrl = $null
$tunnelMode = if ($BackupTunnel) { "backup" } else { "primary" }

if ($tunnelMode -eq "primary") {
    $existingUrl = Get-NgrokActiveUrl -TargetPort $MockPort
    if ($existingUrl) {
        $publicUrl = $existingUrl
        Write-Ok "Tunel ngrok ya activo: $publicUrl"
    }
}

if (-not $publicUrl) {
    $ng = Find-ToolLocation -Name "ngrok"
    if ($tunnelMode -eq "primary" -and -not $ng) {
        Write-WarnMsg "No se encontro 'ngrok'. Usando modo respaldo (cloudflared)."
        $tunnelMode = "backup"
    }

    if ($tunnelMode -eq "primary" -and -not (Test-NgrokAuthtokenConfigured -ToolMode $ng.Mode)) {
        Write-WarnMsg "No se detecto un authtoken configurado para ngrok."
        Write-Host "  1. Obten tu authtoken en: https://dashboard.ngrok.com/get-started/your-authtoken"
        Write-Host "  2. Pegalo abajo y presiona ENTER (solo se hace una vez)."
        Write-Host "  3. Escribe 'backup' para usar cloudflared (URL aleatoria sin cuenta)."
        Write-Host "  4. O presiona ENTER vacio para intentar abrir ngrok de todos modos."
        $ans = (Read-Host "Authtoken / opcion").Trim()
        if ($ans -eq "backup") {
            $tunnelMode = "backup"
        } elseif ($ans) {
            $tokCode = if ($ng.Mode -eq "win") {
                Invoke-LiveNative { & $ng.Path config add-authtoken $ans }
            } else {
                Invoke-LiveNative { & wsl.exe -e ngrok config add-authtoken $ans }
            }
            if ($tokCode -ne 0) {
                throw "No se pudo guardar el authtoken de ngrok."
            }
            Write-Ok "Authtoken de ngrok guardado."
        }
    }

    if ($tunnelMode -eq "primary") {
        Write-Step "Abriendo ventana del tunel ngrok (https://$Domain)..."
        Start-PowerShellWindow -ScriptPath $tunnelScript -WorkingDirectory $MockDir -ScriptArgs @("-Mode", "primary", "-Domain", $Domain, "-Port", "$MockPort", "-SkipTokenPrompt") | Out-Null

        Write-Step "Esperando a que ngrok publique la URL..."
        $deadline = (Get-Date).AddSeconds(20)
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 1
            $publicUrl = Get-NgrokActiveUrl -TargetPort $MockPort
            if ($publicUrl) { break }
        }
        if ($publicUrl) {
            Write-Ok "Tunel ngrok activo: $publicUrl"
        } else {
            Write-WarnMsg "No se pudo leer http://127.0.0.1:4040 todavia. Revisa la ventana del tunel ngrok."
        }
    } else {
        $cfLog = Join-Path $env:TEMP "pc10-cloudflared.log"
        if (Test-Path $cfLog) { Remove-Item $cfLog -Force -ErrorAction SilentlyContinue }
        Write-Step "Abriendo ventana del tunel respaldo (cloudflared)..."
        Start-PowerShellWindow -ScriptPath $tunnelScript -WorkingDirectory $MockDir -ScriptArgs @("-Mode", "backup", "-Port", "$MockPort", "-LogFile", $cfLog) | Out-Null

        Write-Step "Esperando URL publica de cloudflared..."
        $deadline = (Get-Date).AddSeconds(25)
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 1
            if (Test-Path $cfLog) {
                $rawLog = Get-Content -Path $cfLog -Raw -ErrorAction SilentlyContinue
                if ($rawLog -match "(https://[a-zA-Z0-9-]+\.trycloudflare\.com)") {
                    $publicUrl = $Matches[1]
                    break
                }
            }
        }
        if ($publicUrl) {
            Write-Ok "Tunel cloudflared activo: $publicUrl"
        } else {
            Write-WarnMsg "Aun no aparecio la URL en el log; revisa la ventana del tunel."
        }
    }
}

if ($publicUrl) {
    Write-Step "Probando endpoints a traves del tunel publico ($publicUrl)..."
    Start-Sleep -Seconds 1
    $okTunnel = Test-MockEndpoints -BaseUrl $publicUrl -Token $token
    if (-not $okTunnel) {
        Start-Sleep -Seconds 2
        $okTunnel = Test-MockEndpoints -BaseUrl $publicUrl -Token $token
    }
    if ($okTunnel) {
        Write-Ok "Tunel publico verificado al 100%."
    } else {
        Write-WarnMsg "El tunel respondio con error en alguna prueba. Revisa la ventana del tunel."
    }
}

function Show-Summary {
    param([string]$PubUrl, [string]$MockToken, [string]$UiUrl, [int]$MPort)
    $effectiveUrl = if ($PubUrl) { $PubUrl } else { "https://$Domain" }
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  TODO LISTO PARA PROBAR" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  Aplicacion UI : $UiUrl"
    Write-Host "    Login rapido: usuario 'yo'  / clave 'yo'  (admin)"
    Write-Host "    Otros       : admin / Planta-Admin-2026  |  operador / Planta-Operador-2026"
    Write-Host ""
    Write-Host "  Mock Docker   : http://127.0.0.1:$MPort"
    if ($PubUrl) {
        Write-Host "  Tunel publico : $PubUrl"
    } else {
        Write-Host "  Tunel publico : (ver ventana del tunel; esperado $effectiveUrl)" -ForegroundColor Yellow
    }
    Write-Host "  INFO_TOKEN    : $MockToken"
    Write-Host ""
    Write-Host "  Comandos curl para probar el tunel:" -ForegroundColor Cyan
    Write-Host "    curl.exe -i $effectiveUrl/health"
    Write-Host "    curl.exe -i $effectiveUrl/info"
    Write-Host "    curl.exe -i -H `"Authorization: Bearer $MockToken`" $effectiveUrl/info"
    Write-Host "============================================================" -ForegroundColor Green
}

Show-Summary -PubUrl $publicUrl -MockToken $token -UiUrl $uiLocalUrl -MPort $MockPort

while ($true) {
    Write-Host ""
    Write-Host "Opciones:" -ForegroundColor Cyan
    Write-Host "  [1] Abrir UI en el navegador ($uiLocalUrl)"
    Write-Host "  [2] Re-probar Mock local + Tunel publico"
    Write-Host "  [3] Detener todo (Docker + UI + Tunel) y salir"
    Write-Host "  [Enter] Cerrar esta ventana (deja todo corriendo)"
    $choice = (Read-Host "Elige una opcion").Trim()
    if (-not $choice) {
        break
    } elseif ($choice -eq "1") {
        Start-Process $uiLocalUrl | Out-Null
    } elseif ($choice -eq "2") {
        Write-Step "Probando local http://127.0.0.1:$MockPort ..."
        $null = Test-MockEndpoints -BaseUrl "http://127.0.0.1:$MockPort" -Token $token
        $latestPub = Get-NgrokActiveUrl -TargetPort $MockPort
        if ($latestPub) { $publicUrl = $latestPub }
        if ($publicUrl) {
            Write-Step "Probando tunel $publicUrl ..."
            $null = Test-MockEndpoints -BaseUrl $publicUrl -Token $token
        } else {
            Write-WarnMsg "No se detecto URL publica activa para probar."
        }
    } elseif ($choice -eq "3") {
        & (Join-Path $ScriptsDir "stop-all.ps1") -UiPort $UiPort -MockPort $MockPort
        Start-Sleep -Seconds 1
        break
    } else {
        Write-WarnMsg "Opcion no reconocida."
    }
}
