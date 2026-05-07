# Mở cửa sổ PowerShell mới chạy API. Dùng pwsh nếu có, không thì Windows PowerShell 5.1.
$root = Split-Path (Split-Path $PSScriptRoot)
$shell = $null
$p = Get-Command pwsh -ErrorAction SilentlyContinue
if ($p) {
    $shell = $p.Source
} else {
    $shell = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
    if (-not (Test-Path $shell)) { $shell = "powershell.exe" }
}
Start-Process -FilePath $shell -ArgumentList @(
    "-NoProfile",
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $PSScriptRoot "start-server.ps1")
) -WorkingDirectory $root
