# test-robot-music.ps1 — GET /robot/music?probe=1 (chẩn đoán robot_music + thử tải URL).
$ErrorActionPreference = "Stop"

$root = Split-Path (Split-Path $PSScriptRoot)
$port = 8000
$envPath = Join-Path $root ".env"
if (Test-Path $envPath) {
    $line = Get-Content -LiteralPath $envPath -Encoding UTF8 |
        Where-Object { $_ -match '^\s*SERVER_PORT\s*=\s*(\d+)' } |
        Select-Object -First 1
    if ($line -and $line -match '^\s*SERVER_PORT\s*=\s*(\d+)') {
        $port = [int]$Matches[1]
    }
}

$certPath = Join-Path $root "ssl\server.crt"
$useHttps = Test-Path $certPath
$scheme = if ($useHttps) { "https" } else { "http" }
$url = "${scheme}://127.0.0.1:${port}/robot/music?probe=1"

Write-Host "GET $url" -ForegroundColor Cyan

$params = @{
    Uri        = $url
    Method     = "Get"
    TimeoutSec = 60
}
if ($useHttps -and $PSVersionTable.PSVersion.Major -ge 7) {
    $params["SkipCertificateCheck"] = $true
}

try {
    $resp = Invoke-RestMethod @params
} catch {
    Write-Error "Khong goi duoc server. Chay scripts\dev\start-server.ps1 truoc. $_"
    exit 1
}

Write-Host ""
Write-Host "music_dir: $($resp.music_dir)" -ForegroundColor Gray
Write-Host "public_base_effective: $($resp.public_base_effective)" -ForegroundColor $(if ($resp.public_base_effective) { "Green" } else { "Yellow" })
Write-Host "robot_online: $($resp.robot_online)  ROBOT_ENABLED: $($resp.robot_enabled)" -ForegroundColor Gray
Write-Host ""

if ($resp.issues -and $resp.issues.Count -gt 0) {
    Write-Host "ISSUES:" -ForegroundColor Yellow
    $resp.issues | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
    Write-Host ""
}

if ($resp.tracks) {
    Write-Host "TRACKS:" -ForegroundColor White
    foreach ($t in $resp.tracks) {
        Write-Host "  $($t.filename)  ($($t.size_bytes) bytes)" -NoNewline
        if ($t.public_url) { Write-Host "  -> $($t.public_url)" -ForegroundColor DarkCyan }
        else { Write-Host "" }
        if ($t.probe) {
            $p = $t.probe
            if ($p.skipped) {
                Write-Host "    probe: skipped ($($p.reason))" -ForegroundColor DarkGray
            } elseif ($p.ok) {
                Write-Host "    probe: OK HTTP $($p.http_status) $($p.bytes) bytes in $($p.elapsed_ms) ms" -ForegroundColor Green
            } else {
                Write-Host "    probe: FAIL $($p.error) status=$($p.http_status)" -ForegroundColor Red
            }
        }
    }
}

Write-Host ""
Write-Host "Huong dan: sua .env ROBOT_AUDIO_PUBLIC_URL (IP LAN may ban), chay scripts\utils\sync-lan-env.ps1, restart server." -ForegroundColor DarkGray
exit 0
