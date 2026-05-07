# Tạo chứng chỉ tự ký (dev) để uvicorn phục vụ HTTPS (truy cập từ điện thoại / mạng LAN an toàn hơn).
# Cần openssl (Git for Windows: C:\Program Files\Git\usr\bin\openssl.exe).
# Sau khi chạy: khởi động lại server; trên điện thoại mở https://<IP-LAN>:<cổng>/ và chấp nhận cảnh báo chứng chỉ 1 lần.
param(
    [string]$LanIp = "127.0.0.1",
    [int]$Days = 825
)
$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot)
$sslDir = Join-Path $root "ssl"
New-Item -ItemType Directory -Force -Path $sslDir | Out-Null

$openssl = $null
foreach ($c in @("openssl", "C:\Program Files\Git\usr\bin\openssl.exe", "C:\Program Files\OpenSSL-Win64\bin\openssl.exe")) {
    if ($c -eq "openssl") {
        $g = Get-Command openssl -ErrorAction SilentlyContinue
        if ($g) { $openssl = $g.Source; break }
    } elseif (Test-Path $c) { $openssl = $c; break }
}
if (-not $openssl) {
    Write-Host "Không tìm thấy openssl. Cài Git for Windows (có kèm openssl) hoặc thêm openssl vào PATH."
    exit 1
}

$key = Join-Path $sslDir "server.key"
$crt = Join-Path $sslDir "server.crt"
$cnf = Join-Path $sslDir "req.cnf"
# SAN: IP điện thoại sẽ truy cập + localhost (máy tính)
@"
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = alphamini-dev

[v3_req]
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
IP.1 = 127.0.0.1
IP.2 = $LanIp
"@ | Set-Content -Path $cnf -Encoding UTF8

& $openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days $Days `
    -keyout $key -out $crt -config $cnf -extensions v3_req
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Remove-Item $cnf -ErrorAction SilentlyContinue
Write-Host "OK: $crt"
Write-Host "OK: $key"
Write-Host ""
Write-Host "1) Chay lai voi IP may ban: .\scripts\setup\gen-dev-ssl.ps1 -LanIp 10.204.251.130"
Write-Host "2) Khoi dong lai server - tu bat HTTPS khi co ssl\server.crt + ssl\server.key"
Write-Host '3) Tren dien thoai mo: https:// + IP may + :8000/ - chap nhan canh bao chung chi mot lan'
Write-Host '4) .env: ROBOT_AUDIO_PUBLIC_URL=https:// + IP may + :8000 (neu robot can tai MP3)'
