# Chạy Alpha Mini API (FastAPI). OpenClaw: scripts\openclaw\alphamini-openclaw.ps1 (chat | status | scan | behaviors | trigger | …).
# Truoc khi chay: .\scripts\utils\sync-lan-env.ps1 (dong bo ROBOT_AUDIO_PUBLIC_URL voi IP may + cung mang robot).
$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot)
Set-Location $root

# SDK UBTECH (protobuf cũ): tránh lỗi "Descriptors cannot be created directly" với protobuf 4+/5+
$env:PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION = "python"

$py = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Chưa có venv. Chạy: py -3 -m venv venv ; .\venv\Scripts\pip install -r requirements.txt"
    exit 1
}

$port = 8000
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    $line = Get-Content $envFile | Where-Object { $_ -match '^\s*SERVER_PORT\s*=' } | Select-Object -First 1
    if ($line -match '=\s*(\d+)') { $port = [int]$Matches[1] }
}

# Uvicorn: tránh Multiprocess nếu máy có WEB_CONCURRENCY>1 trong biến môi trường user/system
$env:WEB_CONCURRENCY = "1"

function Get-ListenPidsOnPort([int]$TcpPort) {
    $uniq = @{}
    foreach ($c in @(Get-NetTCPConnection -LocalPort $TcpPort -State Listen -ErrorAction SilentlyContinue)) {
        $id = [int]$c.OwningProcess
        if ($id -gt 0) { $uniq[$id] = $true }
    }
    foreach ($line in (netstat -ano 2>$null)) {
        if ($line -notmatch "LISTENING") { continue }
        if ($line -notmatch ":$TcpPort\s") { continue }
        if ($line -notmatch "LISTENING\s+(\d+)\s*$") { continue }
        $id = [int]$Matches[1]
        if ($id -gt 0) { $uniq[$id] = $true }
    }
    return @($uniq.Keys)
}

function Stop-ListenersOnPort([int]$TcpPort) {
    $seen = @{}
    for ($round = 0; $round -lt 6; $round++) {
        $toKill = Get-ListenPidsOnPort -TcpPort $TcpPort
        if (-not $toKill -or $toKill.Count -eq 0) { break }
        foreach ($procId in $toKill) {
            if ($seen.ContainsKey($procId)) { continue }
            $seen[$procId] = $true
            $pn = (Get-Process -Id $procId -ErrorAction SilentlyContinue).ProcessName
            Write-Host "Giai phong cong $TcpPort : taskkill /T PID $procId ($pn)..." -ForegroundColor Yellow
            # /T = ca cay process; taskkill stderr voi Stop se nem loi -> tam tat
            $prevEap = $ErrorActionPreference
            $ErrorActionPreference = "SilentlyContinue"
            & taskkill.exe /F /T /PID $procId 2>$null | Out-Null
            $ErrorActionPreference = $prevEap
        }
        Start-Sleep -Milliseconds 900
    }
}

Stop-ListenersOnPort -TcpPort $port
$stillListen = @(Get-ListenPidsOnPort -TcpPort $port)
# Chi PID con ton tai moi chan lai cong (tranh netstat/OwningProcess stale)
$aliveOnPort = @($stillListen | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
if ($aliveOnPort -and $aliveOnPort.Count -gt 0) {
    $pidList = $aliveOnPort -join ", "
    Write-Host ""
    Write-Host "LOI: cong $port van LISTEN boi process dang chay (PID: $pidList). Uvicorn bind SAU khi robot ket noi - se loi 10048 neu cong bi chiem." -ForegroundColor Red
    Write-Host "Cach xu ly: Task Manager - Details - tim PID - End task; hoac PowerShell Run as administrator." -ForegroundColor Yellow
    Write-Host "Hoac trong .env dat SERVER_PORT=8001 roi chay lai script." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

$sslJson = & $py -c "import sys,json; sys.path.insert(0,r'$root'); import config; print(json.dumps(config.server_ssl_cert_key()))"
if ($sslJson -and $sslJson -ne "null") {
    $pair = $sslJson | ConvertFrom-Json
    if ($pair -and $pair.Count -eq 2) {
        Write-Host "HTTPS: bat (mo https://<IP-LAN>:$port/ neu can truy cap an toan tu thiet bi khac.)"
    }
}
Write-Host ""
Write-Host "Web dieu khien robot: http://127.0.0.1:$port/control  hoac  /ui  (HTTPS: doi http -> https neu da gen ssl)" -ForegroundColor Yellow
Write-Host "API: GET http://127.0.0.1:$port/" -ForegroundColor DarkGray
Write-Host ""
# server.py: bind socket truoc lifespan (uvicorn CLI workers=1 bind sau lifespan -> loi 10048 tren Windows)
Set-Location $root
& $py (Join-Path $root "server.py")
