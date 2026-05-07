# Cài venv + dependencies một lần. SDK robot (`mini`) cài theo hướng dẫn UBTECH nếu import lỗi.
$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot)
Set-Location $root
if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    py -3 -m venv venv
}
& .\venv\Scripts\python.exe -m pip install -U pip
& .\venv\Scripts\pip.exe install -r requirements.txt
Write-Host "OK. Chạy server: .\scripts\dev\start-server.ps1 hoặc .\scripts\dev\start-server-new-window.ps1"
