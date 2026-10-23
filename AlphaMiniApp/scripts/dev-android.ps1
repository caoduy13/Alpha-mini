# USB device: reverse Metro port 8081, then start Metro (optional).
# Usage (from AlphaMiniApp): .\scripts\dev-android.ps1
#   -ResetCache  — npx react-native start --reset-cache
#   -NoMetro     — only adb reverse; start Metro in another terminal

param(
    [switch]$ResetCache,
    [switch]$NoMetro
)

$ErrorActionPreference = "Stop"
$AppRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Write-Host "adb reverse tcp:8081 tcp:8081 ..." -ForegroundColor Cyan
adb reverse tcp:8081 tcp:8081
if ($LASTEXITCODE -ne 0) {
    Write-Host "adb reverse failed. Plug USB, enable debugging, then: adb devices" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`nReverse list:" -ForegroundColor Cyan
adb reverse --list

if ($NoMetro) {
    Write-Host "`n-NoMetro: Metro skipped. Example: cd AlphaMiniApp; npx react-native start" -ForegroundColor Yellow
    exit 0
}

Push-Location $AppRoot
try {
    if ($ResetCache) {
        npx react-native start --reset-cache
    }
    else {
        npx react-native start
    }
}
finally {
    Pop-Location
}
