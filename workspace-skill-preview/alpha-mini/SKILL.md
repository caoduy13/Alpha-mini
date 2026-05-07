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

## Tool: qr_scan

Scan QR using the **robot camera** (sync flow on server). Returns progress text and debug stages in JSON.

- **Method:** POST  
- **Path:** `/chat/qr-scan`  
- **Body:** none — the handler takes **no JSON body** (empty POST). Do **not** send `{"timeout_sec": ...}`; that is not a server parameter today.

```bash
curl -sS -X POST "http://localhost:8000/chat/qr-scan"
```

(v2 Phase 2: optional `X-Alphamini-Token` is **not** applied to this route — only `/chat`, `/robot/trigger`, `/robot/reconnect`.)

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

## Related: QR decode (upload)

- `POST /qr/decode` (multipart `image`) and `POST /qr/decode_base64` use the **existing** `X-API-Key` / `require_api_key` flow — **not** the same as `X-Alphamini-Token`. See `config.py` / `.env` for `AM_SHARED_SECRET` if you call these from a tool.
