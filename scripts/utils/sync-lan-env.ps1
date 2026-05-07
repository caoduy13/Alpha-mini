# Sync ROBOT_AUDIO_PUBLIC_URL to this PC LAN IP on same /16 as ROBOT_IP in .env.
# Run after connecting to the same Wi-Fi as the robot. Then restart scripts\dev\start-server.ps1.
$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot)
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) { Write-Error ".env not found"; exit 1 }

$content = Get-Content -LiteralPath $envFile -Raw -Encoding utf8

if ($content -notmatch '(?m)^\s*ROBOT_IP\s*=\s*(\S+)') {
    Write-Error "ROBOT_IP missing in .env"
    exit 1
}
$robotIp = $Matches[1].Trim()
$oct = $robotIp -split '\.'
if ($oct.Count -lt 2) { Write-Error "Invalid ROBOT_IP: $robotIp"; exit 1 }
$prefix2 = "$($oct[0]).$($oct[1])"
$port = "8000"
if ($content -match '(?m)^\s*SERVER_PORT\s*=\s*(\d+)') { $port = $Matches[1] }

$candidates = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -notlike '127.*' -and
        $_.IPAddress -notlike '169.254.*' -and
        $_.IPAddress.StartsWith("$prefix2.")
    } | Sort-Object -Property IPAddress

$pcIp = $null
if ($candidates) {
    $pcIp = $candidates[0].IPAddress
    Write-Host "OK: PC on same LAN prefix $prefix2.x -> $pcIp ($($candidates[0].InterfaceAlias))"
} else {
    $any = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' }
    if ($any) {
        $pcIp = $any[0].IPAddress
        Write-Warning "No $prefix2.x address on this PC (current IPv4: $pcIp). Join robot Wi-Fi then run this script again."
        Write-Warning "Using current IP for ROBOT_AUDIO_PUBLIC_URL temporarily."
    } else {
        Write-Error "No usable IPv4."
        exit 1
    }
}

$publicUrl = "http://${pcIp}:${port}"
$py = Join-Path $root "venv\Scripts\python.exe"
if (Test-Path $py) {
    try {
        $sslJson = & $py -c "import sys,json; sys.path.insert(0,r'$root'); import config; print(json.dumps(config.server_ssl_cert_key()))" 2>$null
        if ($sslJson -and $sslJson -ne "null") {
            $publicUrl = "https://${pcIp}:${port}"
            Write-Host "Server SSL detected -> ROBOT_AUDIO_PUBLIC_URL uses https:// (robot must fetch MP3 over TLS)"
        }
    } catch {}
}
$newLine = "ROBOT_AUDIO_PUBLIC_URL=$publicUrl"

if ($content -match '(?m)^\s*ROBOT_AUDIO_PUBLIC_URL\s*=') {
    $content = $content -replace '(?m)^\s*ROBOT_AUDIO_PUBLIC_URL\s*=.*$', $newLine
} else {
    $content = $content.TrimEnd() + "`n$newLine`n"
}

Set-Content -LiteralPath $envFile -Value $content -Encoding utf8
Write-Host "Updated .env -> $newLine"
Write-Host "Test: ping $robotIp (should reply when on same network)"
exit 0
