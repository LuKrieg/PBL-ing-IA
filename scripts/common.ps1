# Shared helpers for Windows one-click scripts (PowerShell 5.1 compatible)

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch {}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-WarnMsg {
    param([string]$Message)
    Write-Host "[AVISO] $Message" -ForegroundColor Yellow
}

function Write-ErrMsg {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Invoke-QuietNative {
    param([Parameter(Mandatory = $true)][scriptblock]$Command)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $lines = & $Command 2>&1 | ForEach-Object { $_.ToString() }
        $out = ($lines -join "`n")
        $code = if ($null -ne $LASTEXITCODE) { [int]$LASTEXITCODE } else { 0 }
        return @{ ExitCode = $code; Output = $out }
    } catch {
        return @{ ExitCode = 1; Output = $_.Exception.Message }
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Invoke-LiveNative {
    param([Parameter(Mandatory = $true)][scriptblock]$Command)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Command | Out-Host
        if ($null -ne $LASTEXITCODE) { return [int]$LASTEXITCODE }
        return 0
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Read-EnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$EnvFile,
        [Parameter(Mandatory = $true)][string]$Key
    )
    if (-not (Test-Path $EnvFile)) { return $null }
    foreach ($rawLine in (Get-Content -Path $EnvFile -Encoding UTF8)) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#")) { continue }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { continue }
        $k = $line.Substring(0, $idx).Trim()
        if ($k -eq $Key) {
            $v = $line.Substring($idx + 1).Trim()
            if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
                $v = $v.Substring(1, $v.Length - 2)
            }
            return $v
        }
    }
    return $null
}

function New-RandomHexToken {
    param([int]$Bytes = 32)
    $buf = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($buf)
    } finally {
        $rng.Dispose()
    }
    return ([System.BitConverter]::ToString($buf) -replace "-", "").ToLowerInvariant()
}

function Ensure-MockEnv {
    param([Parameter(Mandatory = $true)][string]$MockDir)
    $envPath = Join-Path $MockDir ".env"
    $token = Read-EnvValue -EnvFile $envPath -Key "INFO_TOKEN"
    if ($token -and $token -ne "change-me") {
        return @{ Path = $envPath; Token = $token; Generated = $false }
    }

    $newToken = New-RandomHexToken -Bytes 32
    $lines = @()
    $replaced = $false
    if (Test-Path $envPath) {
        foreach ($rawLine in (Get-Content -Path $envPath -Encoding UTF8)) {
            if ($rawLine -match "^\s*INFO_TOKEN\s*=") {
                $lines += "INFO_TOKEN=$newToken"
                $replaced = $true
            } else {
                $lines += $rawLine
            }
        }
    }
    if (-not $replaced) {
        $lines += "INFO_TOKEN=$newToken"
    }
    $content = ($lines -join "`n") + "`n"
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($envPath, $content, $utf8NoBom)
    return @{ Path = $envPath; Token = $newToken; Generated = $true }
}

function Test-TcpPort {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [string]$HostName = "127.0.0.1",
        [int]$TimeoutMs = 300
    )
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        $connected = $async.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if (-not $connected) { return $false }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Get-ListeningPids {
    param([Parameter(Mandatory = $true)][int]$Port)
    $pids = @()
    try {
        if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
            $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
            if ($conns) {
                $pids = $conns | ForEach-Object { [int]$_.OwningProcess } | Where-Object { $_ -gt 0 } | Sort-Object -Unique
                return @($pids)
            }
        }
    } catch {}

    $netstatRes = Invoke-QuietNative { netstat -ano -p TCP }
    foreach ($line in ($netstatRes.Output -split "\r?\n")) {
        if ($line -match "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$") {
            $pidVal = [int]$Matches[1]
            if ($pidVal -gt 0 -and ($pids -notcontains $pidVal)) {
                $pids += $pidVal
            }
        }
    }
    return @($pids)
}

function Invoke-HttpCheck {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [string]$Token = "",
        [int]$TimeoutSec = 10
    )
    try {
        $req = [System.Net.HttpWebRequest]::Create($Url)
        $req.Method = "GET"
        $req.Timeout = $TimeoutSec * 1000
        $req.ReadWriteTimeout = $TimeoutSec * 1000
        $req.AllowAutoRedirect = $true
        $req.UserAgent = "pc10-launcher-check/1.0"
        $req.Headers.Add("ngrok-skip-browser-warning", "1")
        if ($Token) {
            $req.Headers.Add("Authorization", "Bearer $Token")
        }

        $resp = [System.Net.HttpWebResponse]$req.GetResponse()
        try {
            $stream = $resp.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            $body = $reader.ReadToEnd()
            return @{ StatusCode = [int]$resp.StatusCode; Body = $body; Error = $null }
        } finally {
            $resp.Close()
        }
    } catch [System.Net.WebException] {
        $webResp = $_.Exception.Response
        if ($webResp) {
            try {
                $httpResp = [System.Net.HttpWebResponse]$webResp
                $stream = $httpResp.GetResponseStream()
                $reader = New-Object System.IO.StreamReader($stream)
                $body = $reader.ReadToEnd()
                return @{ StatusCode = [int]$httpResp.StatusCode; Body = $body; Error = $null }
            } finally {
                $webResp.Close()
            }
        }
        return @{ StatusCode = 0; Body = ""; Error = $_.Exception.Message }
    } catch {
        return @{ StatusCode = 0; Body = ""; Error = $_.Exception.Message }
    }
}

function Wait-HttpReady {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 30
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $res = Invoke-HttpCheck -Url $Url -TimeoutSec 3
        if ($res.StatusCode -eq 200) {
            return $true
        }
        Start-Sleep -Milliseconds 750
    }
    return $false
}

function Test-MockEndpoints {
    param(
        [Parameter(Mandatory = $true)][string]$BaseUrl,
        [Parameter(Mandatory = $true)][string]$Token
    )
    $base = $BaseUrl.TrimEnd("/")
    $checks = @(
        @{ Name = "GET /health -> 200"; Url = "$base/health"; Token = ""; Expected = 200 },
        @{ Name = "GET /info (sin token) -> 401"; Url = "$base/info"; Token = ""; Expected = 401 },
        @{ Name = "GET /info (token invalido) -> 401"; Url = "$base/info"; Token = "wrong-token"; Expected = 401 },
        @{ Name = "GET /info (token valido) -> 200"; Url = "$base/info"; Token = $Token; Expected = 200 }
    )

    $allOk = $true
    foreach ($c in $checks) {
        $res = Invoke-HttpCheck -Url $c.Url -Token $c.Token -TimeoutSec 10
        $ok = ($res.StatusCode -eq $c.Expected)
        if ($ok) {
            Write-Host ("  PASS {0} (HTTP {1})" -f $c.Name, $res.StatusCode) -ForegroundColor Green
        } else {
            $detail = if ($res.Error) { $res.Error } else { "HTTP $($res.StatusCode)" }
            Write-Host ("  FAIL {0} ({1})" -f $c.Name, $detail) -ForegroundColor Red
            $allOk = $false
        }
    }
    return $allOk
}

function Ensure-DockerReady {
    param([int]$TimeoutSeconds = 120)
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCmd) {
        throw "No se encontro 'docker' en PATH. Instala Docker Desktop para Windows."
    }

    $infoRes = Invoke-QuietNative { docker info }
    if ($infoRes.ExitCode -eq 0) {
        return
    }

    $alreadyRunning = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
    if ($alreadyRunning) {
        Write-WarnMsg "Docker Desktop esta abierto pero aun no responde. Esperando al daemon..."
    } else {
        $desktopCandidates = @()
        if ($env:ProgramFiles) { $desktopCandidates += (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe") }
        if (${env:ProgramFiles(x86)}) { $desktopCandidates += (Join-Path ${env:ProgramFiles(x86)} "Docker\Docker\Docker Desktop.exe") }
        if ($env:LOCALAPPDATA) { $desktopCandidates += (Join-Path $env:LOCALAPPDATA "Programs\Docker\Docker\Docker Desktop.exe") }
        $desktopPaths = @($desktopCandidates | Where-Object { $_ -and (Test-Path $_) })

        if ($desktopPaths.Count -gt 0) {
            Write-WarnMsg "Docker no esta respondiendo. Iniciando Docker Desktop..."
            Start-Process -FilePath $desktopPaths[0] | Out-Null
        } else {
            Write-WarnMsg "Docker no esta respondiendo. Esperando a que el daemon de Docker este listo..."
        }
    }

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        $infoRes = Invoke-QuietNative { docker info }
        if ($infoRes.ExitCode -eq 0) {
            Write-Host ""
            Write-Ok "Docker Desktop listo."
            return
        }
        Write-Host "." -NoNewline
    }
    Write-Host ""
    $tailLines = @($infoRes.Output -split "\r?\n" | ForEach-Object { $_.Trim() } | Where-Object { $_ } | Select-Object -Last 3)
    $detail = ($tailLines -join " | ")
    throw "Docker no respondio despues de $TimeoutSeconds segundos. Detalle: $detail"
}

function Find-ToolLocation {
    param([Parameter(Mandatory = $true)][string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) {
        return @{ Mode = "win"; Path = $cmd.Source }
    }
    if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
        $wslRes = Invoke-QuietNative { wsl.exe -e which $Name }
        $wslPath = $wslRes.Output.Trim()
        if ($wslRes.ExitCode -eq 0 -and $wslPath -and ($wslPath -notmatch "has no installed distributions|not found")) {
            return @{ Mode = "wsl"; Path = $wslPath }
        }
    }
    return $null
}

function Get-NgrokConfigPaths {
    $paths = @()
    $checkRes = Invoke-QuietNative { ngrok config check }
    if ($checkRes.Output -match "([A-Za-z]:\\[^\r\n]+?\.ya?ml)") {
        $paths += $Matches[1].Trim().Trim('"')
    }

    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "ngrok\ngrok.yml"),
        (Join-Path $env:APPDATA "ngrok\ngrok.yml"),
        (Join-Path $env:USERPROFILE ".config\ngrok\ngrok.yml"),
        (Join-Path $env:USERPROFILE ".ngrok2\ngrok.yml")
    )
    $msixPattern = Join-Path $env:LOCALAPPDATA "Packages\*\LocalCache\Local\ngrok\ngrok.yml"
    foreach ($item in (Get-ChildItem -Path $msixPattern -ErrorAction SilentlyContinue)) {
        $candidates += $item.FullName
    }

    foreach ($p in $candidates) {
        if ($p -and ($paths -notcontains $p)) {
            $paths += $p
        }
    }
    return $paths
}

function Test-NgrokAuthtokenConfigured {
    param([string]$ToolMode = "win")
    if ($env:NGROK_AUTHTOKEN) { return $true }

    if ($ToolMode -eq "wsl") {
        $wslRes = Invoke-QuietNative { wsl.exe -e bash -lc 'grep -Eq "^[[:space:]]*authtoken:[[:space:]]*[^[:space:]#]+" ~/.config/ngrok/ngrok.yml ~/.ngrok2/ngrok.yml 2>/dev/null && echo OK' }
        return ($wslRes.Output.Trim() -eq "OK")
    }

    foreach ($cfg in (Get-NgrokConfigPaths)) {
        if ($cfg -and (Test-Path $cfg)) {
            $raw = Get-Content -Path $cfg -Raw -ErrorAction SilentlyContinue
            if ($raw -and ($raw -match "(?m)^\s*authtoken:\s*\S+")) {
                return $true
            }
        }
    }
    return $false
}

function Get-NgrokActiveUrl {
    param([int]$TargetPort = 8000)
    $res = Invoke-HttpCheck -Url "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
    if ($res.StatusCode -ne 200 -or -not $res.Body) { return $null }
    try {
        $data = $res.Body | ConvertFrom-Json
        $tunnels = @($data.tunnels)
        $matching = $tunnels | Where-Object { $_.config.addr -match ":$TargetPort\b" }
        if (-not $matching) { $matching = $tunnels }
        $httpsTunnel = $matching | Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1
        if ($httpsTunnel) { return $httpsTunnel.public_url }
        $first = $matching | Select-Object -First 1
        if ($first) { return $first.public_url }
    } catch {}
    return $null
}

function Start-PowerShellWindow {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [string[]]$ScriptArgs = @()
    )
    $quotedArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-NoExit",
        "-File", ('"' + $ScriptPath + '"')
    )
    foreach ($a in $ScriptArgs) {
        if ($a -match '\s') {
            $quotedArgs += ('"' + $a + '"')
        } else {
            $quotedArgs += $a
        }
    }
    return Start-Process -FilePath "powershell.exe" -WorkingDirectory $WorkingDirectory -ArgumentList ($quotedArgs -join " ") -PassThru
}
