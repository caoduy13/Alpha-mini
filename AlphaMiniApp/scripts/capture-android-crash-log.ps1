# Capture crash logs when app closes immediately (Metro can stay running elsewhere).
# Usage: plug USB, USB debugging ON, then:
#   .\scripts\capture-android-crash-log.ps1

$ErrorActionPreference = "Stop"
$pkg = "com.alphaminiapp"

$dev = adb devices | Select-String "device$" | Where-Object { $_ -notmatch "List of devices" }
if (-not $dev) {
    Write-Host "No adb device. Plug USB, enable USB debugging, authorize PC." -ForegroundColor Red
    exit 1
}

$out = Join-Path $PSScriptRoot "..\crash-logcat.txt"
$pidPath = Join-Path $PSScriptRoot "..\crash-dropbox-snippet.txt"

Write-Host "Clearing logcat..." -ForegroundColor Cyan
adb logcat -c 2>$null

Write-Host "Starting logcat recorder -> $out" -ForegroundColor Cyan
$p = Start-Process -FilePath "adb" `
    -ArgumentList @("logcat", "-v", "threadtime") `
    -RedirectStandardOutput $out `
    -RedirectStandardError (Join-Path $PSScriptRoot "..\crash-logcat.err") `
    -PassThru -WindowStyle Hidden

Start-Sleep -Milliseconds 400
adb shell am force-stop $pkg 2>$null
Start-Sleep -Milliseconds 300

Write-Host "Launch $pkg (open app manually if this fails)..." -ForegroundColor Cyan
adb shell am start -n "$pkg/.MainActivity" 2>&1 | Write-Host

Write-Host "Waiting 12s — interact with app if needed..." -ForegroundColor Yellow
Start-Sleep -Seconds 12

Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 400

Write-Host "`n--- Filtered logcat (errors / RN / your package) ---" -ForegroundColor Green
Get-Content $out -ErrorAction SilentlyContinue |
    Select-String -Pattern "FATAL|AndroidRuntime|ReactNativeJS|ReactNative|libc|SIGABRT|$pkg" |
    Select-Object -First 120 |
    ForEach-Object { $_.Line }

Write-Host "`n--- DropBox crash snippet (often works when logcat buffer empty) ---" -ForegroundColor Green
adb shell dumpsys dropbox --print 2>$null |
    Select-String -Pattern "Process: $pkg|Abort message:|AndroidRuntime|FATAL EXCEPTION" -Context 0,25 |
    Select-Object -First 80 |
    Out-File -FilePath $pidPath -Encoding utf8
Get-Content $pidPath -ErrorAction SilentlyContinue

Write-Host "`nFull logcat: $out" -ForegroundColor Cyan
Write-Host "DropBox snippet: $pidPath" -ForegroundColor Cyan
