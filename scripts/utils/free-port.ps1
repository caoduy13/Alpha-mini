# Free TCP listen port (default 8000). Use when WinError 10048.
param([int]$Port = 8000)
$ErrorActionPreference = "SilentlyContinue"
$conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $conns) {
    Write-Host "No LISTEN on port $Port."
    exit 0
}
$ids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($procId in $ids) {
    if ($procId -gt 0) {
        Stop-Process -Id $procId -Force
        Write-Host "Stopped PID $procId (port $Port)."
    }
}
