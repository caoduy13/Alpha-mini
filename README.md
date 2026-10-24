# Alpha Mini Server

## C?i m?i tr??ng server

?? ki?m ch?ng tr?n Windows x64, PowerShell v? Python 3.12. M?i tr??ng ?ang d?ng tr??c ??t n?y l? Python 3.13.12; ch?a ki?m th? l?i to?n b? tr?n Linux/macOS hay robot th?t.

T? th? m?c g?c c?a b?n clone, ch?y l?n l??t:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -r requirements.txt
```

`python` trong c?c l?nh tr?n ph?i tr? t?i Python 3.12. Kh?ng c?n activate venv v? c?c l?nh d?ng ???ng d?n Python c? th?. Requirements hi?n v?n d?ng kho?ng phi?n b?n cho c?c dependency ?? c?, n?n kh?ng ph?i lockfile to?n b? m?i tr??ng.

### SDK UBTECH

Requirements c?i `alphamini==1.2.0` tr?c ti?p t? PyPI, kh?ng c?n l?y wheel trong archive ho?c copy `site-packages` t? m?y c?. ?? ki?m ch?ng t?i/c?i b?ng pip trong venv m?i. Package n?y cung c?p module `mini`; c?c dependency c?a SDK ???c pip c?i t? ??ng.

Metadata c?a package ghi license GPLv3, nh?ng file `alphamini-1.2.0.dist-info/LICENSE` ?i k?m ghi MIT (Copyright 2020 UBTECH). ??y l? s? kh?c bi?t trong ch?nh package; c?n x?c nh?n v?i nh? cung c?p tr??c khi ph?n ph?i l?i SDK. Repo n?y kh?ng ??ng g?i SDK v?o vendor.

SDK c? m? protobuf c?. Ph?i ??t bi?n sau trong **m?i c?a s? PowerShell**, tr??c khi ch?y Python/import server ho?c SDK:

```powershell
$env:PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION = 'python'
```

N?u thi?u bi?n n?y, import SDK ?? t?i hi?n l?i `Descriptors cannot be created directly` v?i protobuf 5.29.6. Bi?n ???c ??t tr??c process, kh?ng ch? th?m v?o `.env`, v? m?t s? import di?n ra tr??c khi server n?p `.env`.

### C?u h?nh

T?o `.env` local t? m?u:

```powershell
Copy-Item .env.example .env
```

?i?n c?u h?nh ri?ng tr?n m?y: `GEMINI_API_KEY`; khi d?ng robot, ki?m tra `ROBOT_ENABLED`, `ROBOT_IP`, `ROBOT_PORT`, `ROBOT_TYPE`, `ROBOT_AUTO_DISCOVER`. C?u h?nh server g?m `SERVER_HOST`, `SERVER_PORT`, `ROBOT_AUDIO_PUBLIC_URL`. README kh?ng ch?a gi? tr? key/token ho?c c?u h?nh robot ri?ng.

HTTPS d?ng `SERVER_SSL_ENABLED`, `SERVER_SSL_CERTFILE`, `SERVER_SSL_KEYFILE`; ch?ng ch?/kh?a local n?m ? `ssl/server.crt` v? `ssl/server.key`. Ch?ng kh?ng c? trong b?n clone. Kh?ng commit `.env` ho?c private key. Ki?m th? b?n d??i d?ng HTTP v? t?t robot, kh?ng c?n t?o ch?ng ch?. Ch?a ki?m ch?ng c?p ch?ng ch? ho?c k?t n?i robot trong quy tr?nh n?y.

### Ki?m tra local kh?ng g?i AI/robot

C?c gi? tr? b?n d??i ch? ph?c v? ki?m tra local; chu?i API key l? gi? tr? gi?, kh?ng ph?i credential. Kh?ng d?ng k?t qu? n?y ?? k?t lu?n AI hay robot ?? k?t n?i ???c.

```powershell
$env:GEMINI_API_KEY = 'offline-import-check-not-a-real-key'
$env:ROBOT_ENABLED = 'false'
$env:SERVER_SSL_ENABLED = 'false'
$env:SERVER_HOST = '127.0.0.1'
$env:SERVER_PORT = '18763'
.\.venv\Scripts\python.exe -B -c "import server"
.\.venv\Scripts\python.exe -B -c "import ws_mini_compat; from mini import mini_sdk; import cv2, numpy; from pyzbar.pyzbar import decode"
```

?? ch?y c? ki?m tra app trong script verify, c?n Node/npm v? dependency app:

```powershell
Push-Location AlphaMiniApp
npm.cmd ci
Pop-Location
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1
```

`npm ci` ph?i ?p d?ng ?? ba patch hi?n c?. Verify ch?y server import, TypeScript v? Jest; hi?n ch?a c? test Python. OpenCV d?ng package headless v? server kh?ng c?n GUI; QR ???c ki?m tra b?ng import OpenCV, NumPy v? pyzbar tr?n Windows.

### Kh?i ch?y

```powershell
.\.venv\Scripts\python.exe -B server.py
```

V?i c?u h?nh ki?m th? tr?n, server ?? tr? HTTP 200 t?i `http://127.0.0.1:18763/openapi.json`. D?ng b?ng Ctrl+C. Khi ch?y th?t, m? c?a s? PowerShell m?i, ??t l?i bi?n t??ng th?ch protobuf, ?i?n `.env` b?ng c?u h?nh ri?ng r?i ch?y c?ng l?nh; kh?ng gi? c?c bi?n ki?m th? gi?. C?c t?ch h?p AI, TTS b?n ngo?i, HTTPS v? robot c?n c?u h?nh/ki?m tra ri?ng.
