# Alpha Mini Server + OpenClaw — ghi chú dự án

## Camera dùng để làm gì? (phân luồng)

| Kênh | File / trang | Nguồn hình | Mục đích |
|------|----------------|------------|----------|
| **Trang web Alpha Mini** | `GET /qr/scan` (trong `server.py`) | **Webcam máy tính** (`getUserMedia`) hoặc **Camera robot** (tab: ảnh JPEG từ `/robot/camera/frame`) | Quét QR (jsQR + upload), không gắn OpenClaw UI. |
| **OpenClaw Control UI** (Chat) | *(Đã gỡ patch UI trong repo.)* Quét QR: chat **«quét qr» / «scan qr»** → server; hoặc tool HTTP **`POST /chat/qr-scan`**. | **Camera robot** qua `https://<host>:<port>/robot/camera/frame` và `POST /robot/qr/from_camera` | Không còn nhúng `openclaw-ui/*.js`; xem `patch-openclaw-ui.ps1` (no-op) và `unpatch-openclaw-ui.ps1`. |
| **Phiên bản tùy chỉnh (ngoài repo chính)** | Có thể đặt bản sao tại `static/alphamini-camera.js` + Tampermonkey load URL | **IP Webcam** (điện thoại) qua proxy `GET /proxy/camera/frame` nếu đã thêm endpoint | Luồng: CORS/mixed content, gửi QR vào chat OpenClaw. *Máy Asus: đã ghi trong **Changelog cá nhân** bên dưới.* Repo gốc có thể chưa có endpoint cho đến khi merge. |

**Tóm lại:** Trong repo này, **camera “chính thức”** gắn OpenClaw là **ảnh từ robot** (SDK chụp từng khung, không có video stream). Trang `/qr/scan` thêm **webcam PC** và **camera robot** là hai tab. Nếu bạn đã mở rộng sang IP Webcam + proxy + gửi chat, hãy giữ code đó cùng ghi chú riêng hoặc merge có chủ đích.

---

## Luồng QR → Gemini (nội dung bất kỳ)

Nội dung quét được từ QR **luôn là chuỗi text** (URL, văn bản thuần, JSON, số điện thoại, v.v.). Khi bạn **đưa chuỗi đó vào cửa sổ chat OpenClaw** (dán tay, hoặc qua script `sendToChat` nếu đã triển khai), **Gemini (agent OpenClaw)** xử lý như một tin nhắn chat bình thường:

- **URL** → có thể tóm tắt, mô tả, hoặc gợi ý bước tiếp (tùy system prompt và công cụ agent).
- **Văn bản / lệnh / JSON** → agent diễn giải hoặc gọi tool theo cấu hình OpenClaw.
- Prefix kiểu `QR Code: ...` chỉ là cách đánh dấu trong UI; có thể đổi trong `sendToChat()` (file camera tùy chỉnh) hoặc chỉnh **`SYSTEM_PROMPT`** trong `config.py` để hướng dẫn cách trả lời khi tin nhắn liên quan QR.

Ví dụ bổ sung `SYSTEM_PROMPT` (chỉnh trong `config.py` hoặc `.env` nếu bạn tách biến):

```text
Khi nhan tin nhan bat dau bang "QR Code:" hoac noi dung tu ma QR:
- Neu la URL: tom tat hoac giai thich ngu canh.
- Neu la lenh/JSON dieu khien robot: uu tien thuc hien qua Alpha Mini neu phu hop.
- Neu la van ban thuong: tra loi tu nhien bang tieng Viet, ngan gon.
```

---

## Môi trường (tham khảo)

- **OS:** Windows  
- **Python:** venv trong thư mục dự án  
- **OpenClaw Control UI (gateway):** mặc định **`http://127.0.0.1:18789`**. Gateway local thường chỉ lắng nghe **HTTP**, không TLS — nếu mở `https://127.0.0.1:18789` trình duyệt báo **`ERR_SSL_PROTOCOL_ERROR`**: đổi sang **`http://`** (cùng cổng). Chỉ dùng `https://...:18789` khi bạn đã bật TLS cho OpenClaw trong cấu hình.  
- **Alpha Mini Server:** `SERVER_PORT` (mặc định 8000), HTTPS nếu có `ssl/server.crt` + `ssl/server.key` hoặc `gen-dev-ssl.ps1` — **khác** URL OpenClaw (8000 vs 18789, thường Alpha Mini HTTPS, OpenClaw HTTP).  

---

## Cấu trúc thư mục (repo)

```
AlphaMiniServer/                    # thư mục gốc repo (đặt tùy máy bạn)
├── server.py              # FastAPI: chat, QR, robot, CORS OpenClaw, …
├── config.py              # GEMINI_*, ROBOT_*, CORS_ALLOW_ORIGINS, SYSTEM_PROMPT, …
├── start-server.ps1       # Chạy uvicorn (+ SSL nếu có ssl/server.crt)
├── ssl/                   # server.crt + server.key (gen-dev-ssl.ps1)
├── static/jsqr.min.js     # Trang /qr/scan
├── robot_music/           # MP3 phục vụ GET /robot/music/{file}
├── openclaw-ui/           # (có thể trống) patch UI đã gỡ
├── patch-openclaw-ui.ps1  # No-op — giữ để script cũ không lỗi
└── .env
```

---

## HTTPS, chứng chỉ, camera

- **getUserMedia** trên `/qr/scan` cần **context an toàn** (HTTPS hoặc localhost). Truy cập bằng `http://<IP-LAN>` thường bị chặn camera.  
- **Self-signed:** mở `https://127.0.0.1:<port>` một lần, chấp nhận cảnh báo, hoặc dùng **mkcert** (`mkcert -install` + tạo cert có SAN cho LAN).  
- **CORS:** `server.py` dùng `CORSMiddleware` với origin OpenClaw (mặc định gồm cả **`http://`** và **`https://`** cho `127.0.0.1` / `localhost` cổng 18789). Xem `CORS_ALLOW_ORIGINS` trong `config.py`.  

---

## Endpoint liên quan QR / robot (tóm tắt)

| Endpoint | Mô tả |
|----------|--------|
| `GET /qr/scan` | Trang quét QR (webcam + camera robot + upload). |
| `POST /qr/decode` | Upload ảnh → giải mã QR (OpenCV). |
| `GET /robot/camera/frame` | JPEG từ camera robot (throttle theo config). |
| `POST /robot/qr/from_camera` | Chụp qua SDK robot → giải mã → JSON `{ ok, count, codes }`. |
| `GET /proxy/camera/frame` | *(Bản mở rộng / máy Asus)* Proxy JPEG từ IP Webcam, bypass CORS cho canvas. |
| `POST /chat` | Chat Gemini (OpenClaw có thể dùng bridge file hoặc gọi trực tiếp tùy cấu hình). |
| `POST /chat/qr-scan` | Quét QR camera robot đồng bộ (JSON `reply` + `stages`) — cấu hình tool HTTP trên OpenClaw. |

---

## OpenClaw: patch UI

```powershell
Set-Location $PSScriptRoot   # thư mục chứa script = gốc repo
.\patch-openclaw-ui.ps1
```

Script hiện **chỉ in hướng dẫn** (UI QR/camera đã gỡ). Mở OpenClaw tại **`http://127.0.0.1:18789`** nếu cần chat gateway; Alpha Mini vẫn tại **`https://<IP-LAN-PC>:<SERVER_PORT>`** khi đã có `ssl/server.crt`.

**Chat → robot:** gõ trong **OpenClaw UI** không tự chạy lệnh trên robot. Alpha Mini chỉ nhận lệnh khi có **POST `/chat`** (vd. `alphamini-openclaw.ps1 "ngồi đi"`) hoặc **file bridge** ghi `OPENCLAW_PENDING_CHAT_PATH` (server đang polling). Nếu robot không phản ứng, kiểm tra luồng này trước khi sửa từ khóa.

---

## Ghi chú phiên bản mở rộng (IP Webcam, Tampermonkey, proxy)

Nếu bạn đã làm theo hội thoại dài (IP Webcam Android, `GET /proxy/camera/frame`, file `static/alphamini-camera.js`, Tampermonkey inject, `sendToChat` gọi React `__reactProps`…), hãy:

- Giữ **code và endpoint proxy** trong cùng nhánh repo hoặc nhánh riêng;  
- Ghi rõ **URL script** Tampermonkey trỏ tới (`/static/...` hay bundle OpenClaw);  
- Tránh trùng **hai lần inject** (dùng `@noframes`, kiểm tra script đã tồn tại trong DOM, hoặc chỉ một cơ chế load).

---

## Changelog cá nhân (mẫu cấu hình — sửa IP theo `.env` của bạn)

### Cấu hình mạng thực tế

- **IP máy tính (LAN):** `<IP-LAN-PC>` (vd. `192.168.10.x` — dùng cho `ROBOT_AUDIO_PUBLIC_URL`, điện thoại mở `https://<IP-LAN-PC>:8000/qr/scan`)
- **IP điện thoại Android (IP Webcam):** `<IP>:8080` nếu dùng IP Webcam + Tampermonkey (mở rộng)
- **IP robot Alpha Mini:** `ROBOT_IP` trong `.env` (vd. `192.168.10.211`)

### SSL Certificate (chuẩn repo)

- **Trong repo:** `ssl/server.crt` và `ssl/server.key` — tạo bằng **`.\gen-dev-ssl.ps1 -LanIp <IP-LAN-PC>`** (OpenSSL; SAN gồm localhost + IP LAN).
- **Tuỳ chọn mkcert:** có thể dùng cặp `certs/cert.pem` + `certs/key.pem` riêng; khi đó đặt `SERVER_SSL_CERTFILE` / `SERVER_SSL_KEYFILE` trong `.env` trỏ tới đường dẫn đầy đủ trên máy bạn.

### Tampermonkey Script

- **Trình duyệt:** Microsoft Edge
- **Tên script:** Alpha Mini Camera (version 2.4)
- **Inject (`@match`):** `http://127.0.0.1:18789/*` — phải **trùng** giao thức với tab OpenClaw (thường **http**). Nếu bạn mở OpenClaw bằng `https://`, đổi `@match` tương ứng.
- **`@noframes`** — tránh inject vào iframe của OpenClaw (đỡ load script hai lần)
- **`unsafeWindow`** — biến guard tồn tại qua SPA navigation
- **URL load:** `https://<IP-LAN-PC>:8000/static/alphamini-camera.js` (đổi host theo máy chạy server)
- **Hook:** `button.text-red-500` (nút QR OpenClaw, SVG `lucide-qr-code`)

### Proxy CORS

- **Endpoint:** `GET https://<IP-LAN-PC>:8000/proxy/camera/frame` *(chưa có trong `server.py` mặc định — bản mở rộng)*
- **Lý do:** IP Webcam (`http://<IP-Webcam>:8080`) không gửi CORS header → canvas bị *tainted* khi vẽ từ `<img>` cross-origin.
- **Cách làm:** `server.py` dùng **httpx** tải ảnh từ `IP_WEBCAM_URL` rồi trả JPEG kèm `Access-Control-Allow-Origin: *` (cần có code endpoint + biến môi trường trên máy này).

### React `onKeyDown` (OpenClaw chat)

- Input chat: `<textarea placeholder="Message Alpha mini...">`
- Không có nút `type="submit"` — gửi bằng phím **Enter**.
- Thứ tự gợi ý:
  1. Native setter `HTMLTextAreaElement.prototype.value`
  2. `InputEvent('input', { bubbles: true })`
  3. Tìm key `__reactProps$...` → `reactProps.onKeyDown(enterEvent)`
- **Delay ~400ms** để React kịp sync state trước khi gửi Enter.

### QR → Chat → Gemini

- Prefix gửi vào chat: `QR Code: <nội dung>`
- Gemini xử lý như tin thường (URL, text, JSON, …); có thể tinh chỉnh **`SYSTEM_PROMPT`** trong `config.py`.

### Các lệnh hay dùng

```powershell
# Kích hoạt venv và chạy server — mở terminal tại thư mục gốc repo (cùng cấp server.py)
# Hoặc: Set-Location "D:\...\AlphaMiniServer"
.\venv\Scripts\Activate.ps1
python server.py

# Kiểm tra CA mkcert trong store
Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Subject -like "*mkcert*" }

# Test proxy camera (Edge)
# https://127.0.0.1:8000/proxy/camera/frame

# Test QR decode — POST multipart ảnh tới (không phải GET trang)
# POST https://127.0.0.1:8000/qr/decode  (field file)

# OpenClaw Control UI (thường HTTP — không dùng https:// nếu báo ERR_SSL_PROTOCOL_ERROR)
# http://127.0.0.1:18789
```

### TODO (chưa làm)

- [ ] Kết nối robot Alpha Mini qua WiFi — cập nhật `ROBOT_IP` trong `.env`
- [ ] Thêm Telegram channel: `openclaw channels add --channel telegram`
- [ ] TTS để robot đọc kết quả QR (Google Cloud TTS / FPT.AI)
- [ ] Cron job buổi sáng gửi tin qua Zalo
- [ ] Lưu lịch sử QR đã quét vào file log
- [ ] Thêm xác thực (auth header) cho `/proxy/camera/frame` nếu expose ra ngoài LAN

---

## OpenClaw — optional skill token (`ALPHAMINI_SKILL_TOKEN`)

**Server (`server.py`):** Nếu biến môi trường `ALPHAMINI_SKILL_TOKEN` **không rỗng** (đặt trong `.env`), các route sau bắt buộc header **`X-Alphamini-Token`** khớp giá trị đó:

- `POST /chat`
- `GET /robot/trigger`
- `POST /robot/reconnect`

**Không** áp dụng cho: `GET /status`, `GET /`, `POST /voice/chat`, `POST /chat/qr-scan`, camera/music/QR decode (`require_api_key` / `X-API-Key` giữ nguyên).

**Nội bộ không bị 401 khi bật token:**

- **File bridge** OpenClaw (`_openclaw_file_bridge_loop`) gọi trực tiếp `process_chat_message()` — không đi qua HTTP `POST /chat` → không qua dependency.
- **`POST /voice/chat`** cũng gọi `process_chat_message()` trực tiếp → không 401.
- **`patch-openclaw-ui.ps1`**: không grep thấy gọi `/chat` hay `/robot/trigger` / reconnect.
- **`openclaw-ui/`**: không grep thấy `fetch` tới các path trên (UI gateway/OpenClaw tách khỏi AlphaMiniServer).
- **`scan-qr.ps1`**: chỉ `POST /chat/qr-scan` — không nằm trong danh sách bảo vệ skill token.

**Caller đã chỉnh:** `alphamini-openclaw.ps1` — khi `$env:ALPHAMINI_SKILL_TOKEN` có giá trị (hoặc đọc từ `.env` cạnh script nếu shell chưa set), mọi `Invoke-RestMethod` tới `/chat`, `/robot/reconnect`, `/robot/trigger` gửi kèm header.

**Skill file:** `workspace-skill-preview/alpha-mini/SKILL.md` (copy vào `~/.openclaw/workspace/skills/alpha-mini/SKILL.md`). Mô tả `curl` với header khi server enforce.

**Kiểm thử nhanh**

1. Để `# ALPHAMINI_SKILL_TOKEN=` trống hoặc xóa dòng — restart server — mọi luồng cũ (Canvas qua bridge, voice, PS1) giữ như trước.
2. Set token trong `.env`, restart server: `curl` `POST /chat` không header → **401**; có `X-Alphamini-Token` đúng → **200**.
3. `alphamini-openclaw.ps1 "thử"` sau khi token bật — script tự đọc `.env` nếu chưa export trong PowerShell.

**Gợi ý triển khai:** Với máy dev chỉ bind `localhost`, có thể để token trống. Bật token khi expose server ra LAN (HTTPS + điện thoại) để hạn chế gọi nhầm `/chat` từ mạng.

---

## Trạng thái / việc tiếp theo (repo)

- Kết nối robot qua WiFi (`ROBOT_IP`, `ROBOT_ENABLED`).
- Tinh chỉnh `SYSTEM_PROMPT` sau khi gửi nội dung QR vào chat.
- Robot TTS / lệnh vật lý: `ROBOT_*` trong `config.py` và route robot trong `server.py`.
- Chi tiết máy Asus (mkcert, Tampermonkey, proxy, React hack): mục **Changelog cá nhân** ở trên.

*File này tóm tắt mục đích camera và luồng QR → Gemini; triển khai IP Webcam/Tampermonkey/proxy là bản mở rộng trên máy cấu hình tương ứng.*
