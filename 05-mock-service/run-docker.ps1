param(
    [int]$Port = 8000,
    [switch]$SkipSmoke,
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"
$MockDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $MockDir
. (Join-Path $RepoRoot "scripts\common.ps1")

try { $Host.UI.RawUI.WindowTitle = "IMACASA PC10 - Mock Service Docker ($Port)" } catch {}

Write-Step "Verificando Docker Desktop..."
Ensure-DockerReady -TimeoutSeconds 120

Write-Step "Verificando archivo .env en 05-mock-service..."
$envInfo = Ensure-MockEnv -MockDir $MockDir
if ($envInfo.Generated) {
    Write-Ok "Se genero un nuevo INFO_TOKEN seguro en 05-mock-service\.env"
} else {
    Write-Ok "INFO_TOKEN cargado desde 05-mock-service\.env"
}

$needBuild = $true
if (-not $Rebuild) {
    $imgRes = Invoke-QuietNative { docker image inspect "pc10-mock-service:1.0.0" --format "{{.Created}}" }
    if ($imgRes.ExitCode -eq 0 -and $imgRes.Output.Trim()) {
        try {
            $rawCreated = ($imgRes.Output.Trim() -replace '(\.\d{1,7})\d*', '$1')
            $imgCreated = [DateTimeOffset]::Parse($rawCreated).LocalDateTime
            $watchPaths = @(
                (Join-Path $MockDir "Dockerfile"),
                (Join-Path $MockDir "compose.yaml"),
                (Join-Path $MockDir "pyproject.toml"),
                (Join-Path $MockDir "uv.lock"),
                (Join-Path $MockDir "app")
            )
            $latestFile = [datetime]::MinValue
            foreach ($wp in $watchPaths) {
                if (-not (Test-Path $wp)) { continue }
                $item = Get-Item $wp
                if ($item.PSIsContainer) {
                    $c = Get-ChildItem $wp -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
                    if ($c -and $c.LastWriteTime -gt $latestFile) { $latestFile = $c.LastWriteTime }
                } elseif ($item.LastWriteTime -gt $latestFile) {
                    $latestFile = $item.LastWriteTime
                }
            }
            if ($latestFile -le $imgCreated) {
                $needBuild = $false
            }
        } catch {}
    }
}

Write-Step $(if ($needBuild) { "Construyendo e iniciando contenedor Docker (pc10-mock-service:1.0.0)..." } else { "Iniciando contenedor Docker (imagen pc10-mock-service:1.0.0 al dia)..." })
Push-Location $MockDir
try {
    $composeCode = if ($needBuild) {
        Invoke-LiveNative { docker compose up --build -d }
    } else {
        Invoke-LiveNative { docker compose up -d }
    }
    if ($composeCode -ne 0) {
        throw "Fallo 'docker compose up' (codigo $composeCode). Si otro servicio (ej. nlp-qa-api) usa el puerto $Port, detenlo primero."
    }
} finally {
    Pop-Location
}

$localUrl = "http://127.0.0.1:$Port"
Write-Step "Esperando a que $localUrl/health responda..."
if (-not (Wait-HttpReady -Url "$localUrl/health" -TimeoutSeconds 30)) {
    throw "El contenedor inicio pero $localUrl/health no respondio 200 en 30s. Revisa 'docker compose logs' en 05-mock-service."
}
Write-Ok "Mock service respondiendo en $localUrl"

if (-not $SkipSmoke) {
    Write-Step "Ejecutando verificacion local (/health y /info)..."
    $passed = Test-MockEndpoints -BaseUrl $localUrl -Token $envInfo.Token
    if (-not $passed) {
        throw "Al menos una verificacion local del mock service fallo."
    }
}

Write-Host ""
Write-Host "Mock service listo:" -ForegroundColor Green
Write-Host "  Local URL : $localUrl"
Write-Host "  INFO_TOKEN: $($envInfo.Token)"
Write-Host "  Prueba    : curl.exe -i -H `"Authorization: Bearer $($envInfo.Token)`" $localUrl/info"
exit 0
