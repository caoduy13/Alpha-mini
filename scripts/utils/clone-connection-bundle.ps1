# Gói tự động mã nguồn + dữ liệu cần để chạy server và kết nối robot/OpenClaw (không gồm venv).
# Dùng: Set-Location thư mục chứa server.py ; .\scripts\utils\clone-connection-bundle.ps1
# Tuỳ chọn: -Destination "D:\backup\AlphaMiniBundle" -IncludeEnv -IncludeSslKey
param(
    [string]$Destination = "",
    [switch]$IncludeEnv,
    [switch]$IncludeSslKey
)

$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot)
Set-Location $root

function Test-PathIsChildOf([string]$Child, [string]$Parent) {
    $c = [System.IO.Path]::GetFullPath($Child.TrimEnd('\', '/'))
    $p = [System.IO.Path]::GetFullPath($Parent.TrimEnd('\', '/'))
    if ($c.Length -le $p.Length) { return $false }
    return $c.StartsWith($p + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}

if (-not $Destination -or [string]::IsNullOrWhiteSpace($Destination)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $parent = Split-Path $root -Parent
    if ([string]::IsNullOrWhiteSpace($parent)) { $parent = $env:TEMP }
    $Destination = Join-Path $parent "AlphaMiniServer-connection-bundle-$stamp"
}

$destRoot = [System.IO.Path]::GetFullPath($Destination)
if (Test-PathIsChildOf -Child $destRoot -Parent $root) {
    Write-Error "Destination must not be inside project root: $destRoot"
    exit 1
}

New-Item -ItemType Directory -Path $destRoot -Force | Out-Null
$copied = [System.Collections.Generic.List[string]]::new()

function Copy-One([string]$RelFromRoot) {
    $src = Join-Path $root $RelFromRoot
    if (-not (Test-Path $src)) { return }
    $dst = Join-Path $destRoot $RelFromRoot
    $parent = Split-Path $dst -Parent
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    Copy-Item -LiteralPath $src -Destination $dst -Force -Recurse
    $copied.Add($RelFromRoot.Replace('\', '/')) | Out-Null
}

# --- Root files (entry/config) ---
foreach ($name in @(
    "server.py",
    "config.py",
    "ws_mini_compat.py",
    "requirements.txt",
    ".env.example",
    ".gitignore"
)) {
    Copy-One $name
}

# --- Structured source folders ---
foreach ($folder in @("scripts", "dances", "docs")) {
    if (Test-Path (Join-Path $root $folder)) { Copy-One $folder }
}

# --- Thư mục phục vụ HTTP / nhạc ---
if (Test-Path (Join-Path $root "static")) { Copy-One "static" }
if (Test-Path (Join-Path $root "robot_music")) { Copy-One "robot_music" }
if (Test-Path (Join-Path $root "openclaw-ui")) {
    $any = Get-ChildItem (Join-Path $root "openclaw-ui") -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($any) { Copy-One "openclaw-ui" }
}

# --- SSL: cert thường cần cho HTTPS LAN; key chỉ khi bạn chủ động bật ---
if (Test-Path (Join-Path $root "ssl")) {
    New-Item -ItemType Directory -Path (Join-Path $destRoot "ssl") -Force | Out-Null
    foreach ($pat in @("*.crt", "*.pem")) {
        foreach ($f in (Get-ChildItem -Path (Join-Path $root "ssl") -File -Filter $pat -ErrorAction SilentlyContinue)) {
            Copy-One ("ssl/" + $f.Name)
        }
    }
    if ($IncludeSslKey) {
        foreach ($f in (Get-ChildItem -Path (Join-Path $root "ssl") -File -Filter "*.key" -ErrorAction SilentlyContinue)) {
            Copy-One ("ssl/" + $f.Name)
        }
    }
    if (Test-Path (Join-Path $root "ssl\.gitignore")) { Copy-One "ssl/.gitignore" }
}

if ($IncludeEnv -and (Test-Path (Join-Path $root ".env"))) {
    Copy-Item -LiteralPath (Join-Path $root ".env") -Destination (Join-Path $destRoot ".env") -Force
    $copied.Add(".env") | Out-Null
}

# --- Manifest JSON ---
$manifest = [ordered]@{
    createdUtc   = (Get-Date).ToUniversalTime().ToString("o")
    sourceRoot   = $root
    destination  = $destRoot
    includeEnv   = [bool]$IncludeEnv
    includeSslKey = [bool]$IncludeSslKey
    copiedPaths  = @($copied | Sort-Object -Unique)
}
$manifestPath = Join-Path $destRoot "bundle-manifest.json"
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $manifestPath -Encoding UTF8

# --- README trong bundle ---
$readme = @"
Alpha Mini Server — gói kết nối (đã copy bằng scripts\utils\clone-connection-bundle.ps1)

Bước tiếp theo trên máy đích:
1) Cài Python 3.11+ ; mở PowerShell tại thư mục này (cùng cấp server.py).
2) py -3 -m venv venv
   .\venv\Scripts\pip install -r requirements.txt
3) Nếu chưa có .env: copy .env.example -> .env và điền GEMINI_API_KEY, ROBOT_IP, ROBOT_AUDIO_PUBLIC_URL (IP LAN máy này, cùng mạng robot).
4) HTTPS (camera điện thoại / robot tải MP3): tạo ssl\server.crt + ssl\server.key — trên máy cũ có thể đã copy cert; nếu thiếu key, chạy lại .\scripts\setup\gen-dev-ssl.ps1 -LanIp <IP-LAN>.
5) .\scripts\utils\sync-lan-env.ps1 (sau khi đổi Wi‑Fi) rồi .\scripts\dev\start-server.ps1

Lưu ý: venv, tts_cache, __pycache__ không nằm trong gói — tạo lại ở máy mới.
"@
if (-not $IncludeEnv) {
    $readme += "`n.env không được gói (bí mật). Chạy lại script với -IncludeEnv nếu bạn chấp nhận copy kèm .env.`n"
}
if (-not $IncludeSslKey) {
    $readme += "`nKhóa ssl\*.key mặc định không gói. Dùng -IncludeSslKey khi cần mang cả private key (cẩn thận).`n"
}
Set-Content -Path (Join-Path $destRoot "CONNECTION_BUNDLE_README.txt") -Value $readme -Encoding UTF8

Write-Host "OK: $($copied.Count) mục (xem bundle-manifest.json). Đích: $destRoot"
