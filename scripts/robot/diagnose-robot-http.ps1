# diagnose-robot-http.ps1 — quét vài cổng HTTP trên robot (tìm file server / gợi ý ROBOT_FILE_HTTP_PORTS).
param(
    [string]$RobotIp = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot)
if (-not $RobotIp) {
    $envPath = Join-Path $root ".env"
    if (Test-Path $envPath) {
        $line = Get-Content -LiteralPath $envPath -Encoding UTF8 |
            Where-Object { $_ -match '^\s*ROBOT_IP\s*=\s*(\S+)' } |
            Select-Object -First 1
        if ($line -and $line -match '^\s*ROBOT_IP\s*=\s*(\S+)') {
            $RobotIp = $Matches[1].Trim()
        }
    }
}

if (-not $RobotIp) {
    Write-Error "Khong tim thay ROBOT_IP. Truyen: .\scripts\robot\diagnose-robot-http.ps1 -RobotIp 10.204.251.163"
    exit 1
}

Write-Host "Scan HTTP tren robot: $RobotIp" -ForegroundColor Cyan
Write-Host ""

$ports = @(80, 8080, 8888, 8000, 8008, 5000, 7080, 9000, 9090, 7070)
$found = @()

foreach ($port in $ports) {
    $uri = "http://${RobotIp}:${port}/"
    try {
        $r = Invoke-WebRequest -Uri $uri -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        $server = if ($r.Headers.Server) { $r.Headers.Server } else { "(no Server header)" }
        Write-Host "OK  Port ${port}: HTTP $($r.StatusCode) | Server: $server" -ForegroundColor Green
        $found += $port
    } catch [System.Net.WebException] {
        $resp = $_.Exception.Response
        if ($resp) {
            $code = [int]$resp.StatusCode
            Write-Host "WARN Port ${port}: HTTP $code (co phan hoi)" -ForegroundColor Yellow
            $found += $port
        } else {
            Write-Host "FAIL Port ${port}: $($_.Exception.Status)" -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "FAIL Port ${port}: timeout / refused" -ForegroundColor DarkGray
    }
}

Write-Host ""
if ($found.Count -gt 0) {
    $csv = ($found | Sort-Object -Unique) -join ","
    Write-Host "Goi y .env:" -ForegroundColor Cyan
    Write-Host "  ROBOT_FILE_HTTP_PORTS=$csv"
    Write-Host ""
    Write-Host "Test lai: GET /robot/camera/frame" -ForegroundColor Cyan
} else {
    Write-Host "Khong thay HTTP server tren cac port thuong gap." -ForegroundColor Yellow
    Write-Host "Firmware co the khong mo file server — thu SDK bytes:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Goi y:" -ForegroundColor Cyan
    Write-Host "  1. pip install -U alphamini"
    Write-Host "  2. .env: ROBOT_IMAGE_FETCH_MODE=sdk_only  (neu chi muon thu response SDK)"
    Write-Host "  3. Restart server va xem log capture: SDK direct / download_failed"
}

exit 0
