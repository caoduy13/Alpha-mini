# Bridge Alpha Mini Server ↔ OpenClaw (exec trên gateway).
# Mặc định: POST /chat. Các lệnh khác: status, scan, connect, behaviors, selftest, trigger, …
#
# Ví dụ:
#   .\scripts\openclaw\alphamini-openclaw.ps1 -FromFile .alphamini_pending_chat.txt
#   .\scripts\openclaw\alphamini-openclaw.ps1 "nhảy đi"
#   .\scripts\openclaw\alphamini-openclaw.ps1 status
#   .\scripts\openclaw\alphamini-openclaw.ps1 scan
#   .\scripts\openclaw\alphamini-openclaw.ps1 connect
#   .\scripts\openclaw\alphamini-openclaw.ps1 behaviors
#   .\scripts\openclaw\alphamini-openclaw.ps1 selftest
#   .\scripts\openclaw\alphamini-openclaw.ps1 reconnect
#   .\scripts\openclaw\alphamini-openclaw.ps1 trigger -Cmd mixi
#   .\scripts\openclaw\alphamini-openclaw.ps1 trigger -Cmd dance -Behavior dance_0004
#   .\scripts\openclaw\alphamini-openclaw.ps1 trigger -Cmd audio -Url "https://example.com/song.mp3"
#   .\scripts\openclaw\alphamini-openclaw.ps1 tts_test -Text "Hello" -TtsVia http
#   .\scripts\openclaw\alphamini-openclaw.ps1 tts_test Xin chao
# Biến môi trường: ALPHAMINI_SERVER_URL (mặc định http://127.0.0.1:8000)

param(
    [Parameter(Position = 0, HelpMessage = "Nếu là từ khóa lệnh (status, scan, …) thì gọi API tương ứng; không thì coi là nội dung chat.")]
    [string]$First = "",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest = @(),
    [string]$FromFile = "",
    [string]$Text = "",
    [string]$Cmd = "",
    [string]$Behavior = "",
    [string]$Url = "",
    [bool]$Speak = $true,
    # tts_test: http | sdk | để trống (theo ROBOT_TTS_MODE trên server)
    [string]$TtsVia = ""
)

$ErrorActionPreference = "Stop"

# Nếu chưa export ALPHAMINI_SKILL_TOKEN trong shell, đọc từ .env ở project root.
$root = Split-Path (Split-Path $PSScriptRoot)
$_amEnvFile = Join-Path $root ".env"
if (-not $env:ALPHAMINI_SKILL_TOKEN -and (Test-Path -LiteralPath $_amEnvFile)) {
    foreach ($_line in Get-Content -LiteralPath $_amEnvFile -Encoding utf8) {
        $_s = $_line.Trim()
        if (-not $_s -or $_s.StartsWith("#")) { continue }
        if ($_s -match '^\s*ALPHAMINI_SKILL_TOKEN\s*=\s*(.+)\s*$') {
            $_v = $Matches[1].Trim().Trim('"').Trim("'")
            if ($_v) { $env:ALPHAMINI_SKILL_TOKEN = $_v }
            break
        }
    }
}

function Invoke-AlphaMiniRest {
    param([hashtable]$RestParams)
    $tok = $env:ALPHAMINI_SKILL_TOKEN
    if ($tok -and $tok.Trim()) {
        if (-not $RestParams.ContainsKey("Headers")) { $RestParams["Headers"] = @{} }
        $RestParams.Headers["X-Alphamini-Token"] = $tok.Trim()
    }
    Invoke-RestMethod @RestParams
}

$verbs = @(
    "status", "scan", "connect", "reconnect", "behaviors", "selftest", "trigger", "tts_test", "help"
)
$action = "chat"
if ($First) {
    $fv = $First.ToLowerInvariant()
    if ($verbs -contains $fv) {
        $action = $fv
    }
    else {
        $parts = @($First) + $Rest
        $Text = ($parts -join " ").Trim()
    }
}
elseif ($Rest -and $Rest.Count -gt 0) {
    $Text = ($Rest -join " ").Trim()
}

if ($FromFile) {
    if (-not (Test-Path -LiteralPath $FromFile)) {
        Write-Error "FromFile not found: $FromFile"
        exit 1
    }
    $Text = Get-Content -LiteralPath $FromFile -Raw -Encoding utf8
}

if ($action -eq "tts_test" -and [string]::IsNullOrWhiteSpace($Text) -and ($Rest -and $Rest.Count -gt 0)) {
    $Text = ($Rest -join " ").Trim()
}

$base = $env:ALPHAMINI_SERVER_URL
if (-not $base) { $base = "http://127.0.0.1:8000" }
$base = $base.TrimEnd("/")

function Show-AlphaMiniHelp {
    @"
Alpha Mini — OpenClaw bridge

  (mặc định)  POST /chat — cần -Text, -FromFile, hoặc tham số vị trí là câu chat
  status      GET  /status
  scan        GET  /robot/scan
  connect     POST /robot/connect (chọn thiết bị đầu tiên)
  reconnect   POST /robot/reconnect
  behaviors   GET  /robot/behaviors (danh sách vũ đạo / behavior)
  selftest    GET  /robot/selftest
  tts_test    GET  /robot/tts_test — robot phát thử TTS (-Text; -TtsVia http|sdk)
  trigger     GET  /robot/trigger — cần -Cmd; tùy chọn -Behavior, -Url (nhạc)
  help        In ra hướng dẫn này

Trigger -Cmd: mixi (An Độ Mixi — nhạc + vũ đạo v3), dance, left, right, forward, stop, greet, sit, stand, audio (kèm -Url)

Biến: ALPHAMINI_SERVER_URL = $base
  ALPHAMINI_SKILL_TOKEN — nếu server bật enforcement (.env), script đọc từ .env cạnh file hoặc từ biến môi trường; gửi header X-Alphamini-Token khi gọi /chat, /robot/reconnect, /robot/trigger.
"@
}

if ($action -eq "help") {
    Show-AlphaMiniHelp
    exit 0
}

if ($action -eq "chat") {
    if ([string]::IsNullOrWhiteSpace($Text)) {
        Write-Error "Chat cần -Text, -FromFile, hoặc câu ở tham số vị trí. Gõ: alphamini-openclaw.ps1 help"
        exit 1
    }
    $body = @{ text = $Text.Trim(); speak = $Speak } | ConvertTo-Json -Compress
    $resp = Invoke-AlphaMiniRest @{
        Uri         = "$base/chat"
        Method      = "Post"
        ContentType = "application/json; charset=utf-8"
        Body        = $body
    }
    # Trả về để OpenClaw hiển thị tool output (rút gọn để UI không bị ẩn/khó đọc).
    $out = @{
        reply = $resp.reply
        robot_online = $resp.robot_online
        action_detected = $resp.action_detected
        robot_action_ok = $resp.robot_action_ok
        robot_action_error = $resp.robot_action_error
    }
    $out | ConvertTo-Json -Depth 6 -Compress
    exit 0
}

switch ($action) {
    "status" {
        Invoke-RestMethod -Uri "$base/status" -Method Get
    }
    "scan" {
        Invoke-RestMethod -Uri "$base/robot/scan" -Method Get
    }
    "connect" {
        Invoke-RestMethod -Uri "$base/robot/connect" -Method Post -ContentType "application/json; charset=utf-8" -Body "{}"
    }
    "reconnect" {
        Invoke-AlphaMiniRest @{
            Uri         = "$base/robot/reconnect"
            Method      = "Post"
            ContentType = "application/json; charset=utf-8"
            Body        = "{}"
        }
    }
    "behaviors" {
        Invoke-RestMethod -Uri "$base/robot/behaviors" -Method Get
    }
    "selftest" {
        Invoke-RestMethod -Uri "$base/robot/selftest" -Method Get
    }
    "tts_test"      {
        if ([string]::IsNullOrWhiteSpace($Text)) { $Text = "Xin chao ban" }
        $enc = [uri]::EscapeDataString($Text.Trim())
        $q = "text=$enc"
        $via = if ($TtsVia) { $TtsVia.Trim().ToLowerInvariant() } else { "" }
        if ($via -eq "http" -or $via -eq "sdk") {
            $q += "&via=$([uri]::EscapeDataString($via))"
        }
        Invoke-RestMethod -Uri "$base/robot/tts_test?$q" -Method Get
    }
    "trigger" {
        if ([string]::IsNullOrWhiteSpace($Cmd)) {
            Write-Error "trigger cần -Cmd (vd: dance, left, forward, audio). Xem: alphamini-openclaw.ps1 help"
            exit 1
        }
        $q = "cmd=$([uri]::EscapeDataString($Cmd.Trim()))"
        if ($Behavior) { $q += "&behavior=$([uri]::EscapeDataString($Behavior.Trim()))" }
        if ($Url) { $q += "&url=$([uri]::EscapeDataString($Url.Trim()))" }
        Invoke-AlphaMiniRest @{
            Uri    = "$base/robot/trigger?$q"
            Method = "Get"
        }
    }
}
