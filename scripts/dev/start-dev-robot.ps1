$ErrorActionPreference = "Stop"

$root = Split-Path (Split-Path $PSScriptRoot)
$appDir = Join-Path $root "AlphaMiniApp"

if (-not (Test-Path $appDir)) {
    Write-Host "Khong tim thay AlphaMiniApp tai: $appDir" -ForegroundColor Red
    exit 1
}

$deviceId = (& adb devices | Select-String "device$" | Select-Object -First 1).ToString().Split("`t")[0].Trim()
if (-not $deviceId) {
    Write-Host "Khong tim thay thiet bi ADB. Hay cam USB va bat USB debugging." -ForegroundColor Red
    exit 1
}

Write-Host "ADB device: $deviceId" -ForegroundColor Cyan

# Ensure Metro is running for React Native debug.
$listen8081 = Get-NetTCPConnection -LocalPort 8081 -State Listen -ErrorAction SilentlyContinue
if (-not $listen8081) {
    Write-Host "Dang khoi dong Metro (port 8081)..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command", "Set-Location '$appDir'; npm start"
    ) | Out-Null

    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Milliseconds 1000
        $listen8081 = Get-NetTCPConnection -LocalPort 8081 -State Listen -ErrorAction SilentlyContinue
        if ($listen8081) { break }
    }
}

if (-not $listen8081) {
    Write-Host "Metro chua len port 8081. Thu chay tay: cd AlphaMiniApp; npm start" -ForegroundColor Red
    exit 1
}

Write-Host "Metro OK tren 8081" -ForegroundColor Green

& adb -s $deviceId reverse --remove-all | Out-Null
& adb -s $deviceId reverse tcp:8081 tcp:8081 | Out-Null
Write-Host "ADB reverse tcp:8081 -> tcp:8081 da thiet lap." -ForegroundColor Green

Set-Location $appDir
Write-Host "Dang cai/chay app debug..." -ForegroundColor Yellow
& npm run android
