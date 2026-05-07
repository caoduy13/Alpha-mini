# Hoan tac patch: khoi phuc index.html tu .bak-before-alphamini-qr
param([string]$OpenclawIndex = "")
$ErrorActionPreference = "Stop"
function Find-OpenclawIndex {
    param([string]$Explicit)
    if ($Explicit -and (Test-Path $Explicit)) { return (Resolve-Path $Explicit).Path }
    $candidates = @()
    try {
        $nr = & npm root -g 2>$null
        if ($nr) { $candidates += (Join-Path $nr.Trim() "openclaw\dist\control-ui\index.html") }
    } catch {}
    $candidates += (Join-Path $env:APPDATA "npm\node_modules\openclaw\dist\control-ui\index.html")
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) { return (Resolve-Path $p).Path }
    }
    return $null
}
$idx = Find-OpenclawIndex -Explicit $OpenclawIndex
if (-not $idx) { Write-Host "Khong tim thay index.html OpenClaw."; exit 1 }
$bak = $idx + ".bak-before-alphamini-qr"
if (-not (Test-Path $bak)) { Write-Host "Khong co backup: $bak"; exit 1 }
Copy-Item -LiteralPath $bak -Destination $idx -Force
Write-Host "OK: da khoi phuc tu backup."
