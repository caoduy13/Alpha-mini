---
name: alpha-mini
description: |
  Control the physical Alpha Mini humanoid robot via the AlphaMiniServer HTTP API.
  Use when the user wants the robot to speak, move, perform built-in actions,
  scan QR codes, or report status. Requires AlphaMiniServer running at the
  base URL below and robot on the same Wi-Fi.
---

# Alpha Mini control

## Base URL

Default: `http://localhost:8000`. Override via skill env var `ALPHAMINI_BASE_URL` (prepend to paths below if your deployment differs).

## Authentication

If the **server** has env `ALPHAMINI_SKILL_TOKEN` set (after Phase 2), include header on protected routes:

`X-Alphamini-Token: <same value as ALPHAMINI_SKILL_TOKEN in .env>`

If `ALPHAMINI_SKILL_TOKEN` is unset or empty on the server, no header is required (dev).

Protected routes (when token is set): `POST /chat`, `GET /robot/trigger`, `POST /robot/reconnect` only.

Repo helper `alphamini-openclaw.ps1` reads `ALPHAMINI_SKILL_TOKEN` from `.env` next to the script (if not already in the process environment) and sends `X-Alphamini-Token` for those three calls.

## Tool: chat

Natural-language entry point. Server parses intent (keywords first, optional Gemini fallback), may trigger robot actions, returns JSON with `reply`, `robot_online`, etc. Optional robot TTS when `speak=true` and server config allows it.

- **Method:** POST  
- **Path:** `/chat`  
- **Body (JSON):** `{"text": "<user text>", "speak": true}` — field name is **`text`**, not `message`.

```bash
curl -sS -H "Content-Type: application/json" \
  -H "X-Alphamini-Token: $TOKEN" \
  -d "{\"text\":\"robot vẫy tay\",\"speak\":true}" \
  "http://localhost:8000/chat"
```

(Omit `X-Alphamini-Token` when server token is not configured.)

## Tool: trigger

Discrete command when you know the exact action.

- **Method:** GET  
- **Path:** `/robot/trigger?cmd=<name>`  
- **Commands (examples):** `mixi`, `dance`, `left`, `right`, `forward`, `stop`, `greet`, `sit`, `stand`, and `audio` with `&url=<url-encoded mp3>`  
- See `GET /` or server logs for full error messages if a command is rejected.

```bash
curl -sS -H "X-Alphamini-Token: $TOKEN" \
  "http://localhost:8000/robot/trigger?cmd=greet"
```

## Tool: status

Health and configuration snapshot before other calls.

- **Method:** GET  
- **Path:** `/status`  
- **No** skill token required (even when `ALPHAMINI_SKILL_TOKEN` is set).

```bash
curl -sS "http://localhost:8000/status"
```

## Tool: tts_test

Quick TTS verification on the robot path.

- **Method:** GET  
- **Path:** `/robot/tts_test`  
- No skill token in Phase 2 spec (unchanged from current server).

```bash
curl -sS "http://localhost:8000/robot/tts_test"
```

## Tool: reconnect

Use when `/status` shows `robot_online: false` or after Wi-Fi changes.

- **Method:** POST  
- **Path:** `/robot/reconnect`  
- **Body:** none required.

```bash
curl -sS -X POST -H "X-Alphamini-Token: $TOKEN" \
  "http://localhost:8000/robot/reconnect"
```

## Tool: qr_scan (robot camera)

Capture one SDK frame from the **robot camera**, decode QR/barcode (pyzbar + OpenCV fallback), optionally forward decoded text to Gemini (`auto_chat`). Same behavior as the legacy path; prefer the clearer alias when documenting tools.

- **Method:** POST  
- **Paths (equivalent):**  
  - `/robot/qr/from_camera` — preferred alias (matches `docs/PROJECT_NOTE.md`).  
  - `/chat/qr-scan` — backward-compatible name.  
- **Query:** optional `auto_chat` = `true` | `false`. Omit = use server env `QR_AUTO_CHAT` (default true). When true, server forwards `"QR Code: <text>"` into the Gemini chat session after a successful decode.  
- **Body:** none (empty POST).

```bash
curl -sS -X POST "http://localhost:8000/robot/qr/from_camera?auto_chat=true"
curl -sS -X POST "http://localhost:8000/chat/qr-scan"
```

These routes do **not** require `X-Alphamini-Token` (same as `GET /status`). Protected routes when token is set remain: `POST /chat`, `GET /robot/trigger`, `POST /robot/reconnect`.

**Natural language:** `POST /chat` with text like «quét qr», «scan qr» runs the same scan flow in-process (with Gemini forwarding controlled by `QR_AUTO_CHAT`); use POST endpoints above when you want a structured JSON scan result without composing Vietnamese phrases.

## Tool: qr_decode (upload image)

Decode QR from a **local/host image** (no robot camera). Multipart field name **`file`**.

- **Method:** POST  
- **Path:** `/qr/decode`  
- **Body:** `multipart/form-data` with `file=@image.jpg`  
- **No** skill token required.

```bash
curl -sS -F "file=@qr.jpg" "http://localhost:8000/qr/decode"
```

## Tool: qr_decode_base64

Decode QR from **base64** image (e.g. browser canvas). JSON body.

- **Method:** POST  
- **Path:** `/qr/decode_base64`  
- **Body (JSON):** `{"image_b64": "<data URL or raw base64>", "source": "pc"}` (`source` optional label for server QR history).

```bash
curl -sS -H "Content-Type: application/json" \
  -d "{\"image_b64\":\"data:image/jpeg;base64,/9j/4AAQ...\",\"source\":\"openclaw\"}" \
  "http://localhost:8000/qr/decode_base64"
```

## Tool: qr_history

List or clear persisted QR scan history (JSONL on server; see env `QR_HISTORY_PATH`).

- **Method:** GET — `/qr/history?limit=50`  
- **Method:** DELETE — `/qr/history` (clear file + in-memory cache)  
- **No** skill token required.

```bash
curl -sS "http://localhost:8000/qr/history?limit=50"
curl -sS -X DELETE "http://localhost:8000/qr/history"
```

## Tool: qr_scan_page (human UI)

Browser page with webcam, robot camera tab, and upload — **not** ideal as an automated HTTP “tool” unless headless; document so agents know users can open it.

- **Method:** GET  
- **Path:** `/qr/scan`

## Tool: camera_frame

JPEG still from robot camera (polling / SDK).

- **Method:** GET  
- **Path:** `/robot/camera/frame`  
- Returns **JPEG bytes** (not JSON).

```bash
curl -sS -o frame.jpg "http://localhost:8000/robot/camera/frame"
```

## Safety rules

- Prefer `GET /status` first if you have not confirmed the robot this session.
- Do not chain many movement commands without user confirmation.
- Avoid calling `POST /robot/reconnect` repeatedly; wait after Wi-Fi or server restarts.
- Keep user text for TTS reasonable; very long replies may be truncated server-side.
- If `chat` indicates robot offline, report clearly and suggest Wi-Fi / `ROBOT_IP` / `reconnect`; do not silently retry in a tight loop.

## Related docs

- Server QR behavior and env (`QR_AUTO_CHAT`, history path, dedupe): `docs/QR_FEATURE.md`, `docs/PROJECT_NOTE.md`.
