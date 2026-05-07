"""
server.py — Alpha Mini AI Chatbot Bridge Server
================================================
FastAPI + WebSocket bridge kết nối Flutter app ↔ AI (Gemini/OpenAI) ↔ Alpha Mini robot.

Cách chạy:
    uvicorn server:app --host 0.0.0.0 --port 8000 --reload

Endpoints:
    GET  /status          → trạng thái server + robot + AI
    GET  /history         → lịch sử hội thoại hiện tại
    POST /chat            → gửi tin nhắn qua REST (test)
    WS   /ws/chat         → WebSocket cho Flutter app
    WS   /ws/xiaozhi      → WebSocket Xiaozhi (SelfHost: ws://IP:8000/ws/xiaozhi)
"""

import asyncio
import json
import logging
import time
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import socket

import unicodedata
from pathlib import Path
from config import SERVER_HOST, SERVER_PORT, SERVER_LOCAL_IP, KEYWORD_ACTION_MAP, MUSIC_KEYWORD_MAP
from ai_service import AIService
from robot_controller import RobotController
from xiaozhi_handler import handle_xiaozhi_websocket

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/server.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("Server")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Alpha Mini AI Chatbot Server",
    description="AI-powered chatbot bridge: Flutter App ↔ Gemini/GPT ↔ Alpha Mini Robot",
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve TTS audio files cho robot download
os.makedirs("static/audio", exist_ok=True)
app.mount("/audio", StaticFiles(directory="static/audio"), name="audio")

# Serve music files
os.makedirs("static/music", exist_ok=True)
app.mount("/music", StaticFiles(directory="static/music"), name="music")

# ── Singleton services ────────────────────────────────────────────────────────
ai    = AIService()
robot = RobotController()

# ── WebSocket client management ───────────────────────────────────────────────
ws_clients: Set[WebSocket] = set()
start_time = time.time()

# ── UDP discovery (tự tìm server trong LAN) ──────────────────────────────────
DISCOVERY_PORT = 54545
DISCOVERY_MAGIC = b"ALPHAMINI_DISCOVER"


# ── Startup / Shutdown ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    log.info("=" * 50)
    log.info("   Alpha Mini AI Chatbot Server starting…")
    log.info("=" * 50)

    # Kết nối robot (chạy background, không block server start)
    asyncio.create_task(_connect_robot())

    # Bật UDP discovery để app di động tự tìm server trong cùng WiFi
    asyncio.create_task(_start_discovery_server())


async def _connect_robot():
    success = await robot.connect()
    if success:
        # Chào hỏi ban đầu
        await robot.respond(
            "Xin chào! Tôi là Alpha Mini. Bạn muốn nói chuyện về điều gì?",
            "wave"
        )
        # Bật lắng nghe giọng nói từ microphone robot
        await robot.start_listening(_on_robot_speech)
    else:
        log.warning("Running without robot (demo mode). AI still functional.")


@app.on_event("shutdown")
async def shutdown():
    await robot.disconnect()
    log.info("Server shutdown complete.")


async def _start_discovery_server():
    """
    UDP discovery server:
    - App gửi gói "ALPHAMINI_DISCOVER" tới broadcast:port 54545
    - Server trả lại JSON: {"name": "...", "ip": SERVER_LOCAL_IP, "port": SERVER_PORT}
    """
    loop = asyncio.get_running_loop()

    class _DiscoveryProtocol(asyncio.DatagramProtocol):
        def __init__(self):
            self.transport = None

        def connection_made(self, transport):
            self.transport = transport
            log.info(f"🔍 UDP discovery listening on 0.0.0.0:{DISCOVERY_PORT}")

        def datagram_received(self, data, addr):
            try:
                if data.strip() != DISCOVERY_MAGIC:
                    return
                resp = json.dumps({
                    "name": "AlphaMini Bridge Server",
                    "ip": SERVER_LOCAL_IP,
                    "port": SERVER_PORT,
                    "time": int(time.time()),
                }).encode("utf-8")
                self.transport.sendto(resp, addr)
            except Exception as e:
                log.warning(f"Discovery datagram error: {e}")

    await loop.create_datagram_endpoint(
        _DiscoveryProtocol,
        local_addr=("0.0.0.0", DISCOVERY_PORT),
        allow_broadcast=True,
    )


# ── Music helpers ─────────────────────────────────────────────────────────────

MUSIC_DIR = Path("static/music")
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

# Ánh xạ tên bài hát → query YouTube
SONG_PRESETS: dict[str, str] = {
    "sexy love":           "T-ara Sexy Love official audio",
    "t-ara":               "T-ara Sexy Love official audio",
    "bopeep":              "T-ara Bo Peep Bo Peep official audio",
    "lovey dovey":         "T-ara Lovey Dovey official audio",
    "gangnam style":       "Psy Gangnam Style official audio",
    "sorry sorry":         "Super Junior Sorry Sorry official audio",
    # Jiafei - Ye Hua Xiang (野花香)
    "jiafei ye hua xiang": "Jiafei 野花香 Ye Hua Xiang official audio",
    # Bài Tết sôi động (id = gU3lD2rNA9s)
    "tet_chuc_tet":        "gU3lD2rNA9s",
}


async def _download_youtube_audio(query: str) -> str | None:
    """
    Download audio từ YouTube theo query, cache vào MUSIC_DIR.
    Nếu file đã tồn tại (cache), dùng lại không tải lại.
    Trả về URL phục vụ từ server, hoặc None nếu lỗi.
    """
    try:
        import yt_dlp

        def _ydl_get_or_download():
            # Bước 1: lấy thông tin video (không download) để biết id
            # Dùng định dạng rất rộng để tránh lỗi "Requested format is not available"
            base_opts = {
                "format": "bestaudio/best",
                "quiet": True,
                "no_warnings": True,
            }
            info_opts = {**base_opts, "skip_download": True}

            with yt_dlp.YoutubeDL(info_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                entry = info["entries"][0] if info.get("entries") else info
                vid_id = entry["id"]
                title  = entry.get("title", "")

            # Bước 2: kiểm tra cache — tìm bất kỳ file nào khớp vid_id
            cached = list(MUSIC_DIR.glob(f"{vid_id}.*"))
            if cached:
                cached_file = cached[0]
                log.info(f"🎵 Using cached: {cached_file.name}")
                return vid_id, cached_file.suffix.lstrip("."), title

            # Bước 3: chưa có → download
            dl_opts = {
                **base_opts,
                "outtmpl": str(MUSIC_DIR / "%(id)s.%(ext)s"),
                "quiet": False,
            }
            with yt_dlp.YoutubeDL(dl_opts) as ydl:
                dl_info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                dl_entry = dl_info["entries"][0] if dl_info.get("entries") else dl_info
                return dl_entry["id"], dl_entry["ext"], dl_entry.get("title", "")

        loop = asyncio.get_event_loop()
        vid_id, ext, title = await loop.run_in_executor(None, _ydl_get_or_download)
        url = f"http://{SERVER_LOCAL_IP}:{SERVER_PORT}/music/{vid_id}.{ext}"
        log.info(f"🎵 Music ready: '{title}' → {url}")
        return url

    except Exception as e:
        log.error(f"YouTube download error: {e}")
        return None


# ── Keyword detection ─────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Chuẩn hóa text: lowercase, bỏ dấu → dễ so khớp keyword."""
    text = text.lower()
    # Bỏ dấu tiếng Việt để khớp cả "nhảy" lẫn "nhay"
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _detect_action_keywords(text: str) -> list[str]:
    """
    Tìm action ID khớp tốt nhất với keyword trong text.
    Ưu tiên keyword dài nhất (cụ thể nhất). Trả về tối đa 1 action.
    """
    norm = _normalize(text)
    best_kw = ""
    best_action = ""

    # Sắp xếp keyword dài → ngắn, chọn keyword dài nhất match đầu tiên
    for kw, action_id in sorted(KEYWORD_ACTION_MAP.items(), key=lambda x: -len(x[0])):
        kw_norm = _normalize(kw)
        if kw_norm in norm and len(kw) > len(best_kw):
            best_kw = kw
            best_action = action_id

    if best_action:
        log.info(f"🎯 Keyword detected: '{best_kw}' → action '{best_action}'")
        return [best_action]
    return []


# ── Core pipeline: giọng nói/text → AI → robot ───────────────────────────────

async def _process_message(user_text: str, source: str = "app") -> dict:
    """
    Trung tâm xử lý: nhận text → gửi AI → robot phản hồi → broadcast app.
    source: "robot" (giọng nói) | "app" (gõ phím)
    """
    log.info(f"[{source.upper()}] User: {user_text}")

    # Gửi "đang suy nghĩ" tới tất cả app
    await _broadcast({"type": "thinking", "user": user_text})

    # ── Phát hiện keyword bài hát → play music + dance ───────────────────────
    norm_text = _normalize(user_text)
    for music_kw, song_name in sorted(MUSIC_KEYWORD_MAP.items(), key=lambda x: -len(x[0])):
        if _normalize(music_kw) in norm_text:
            log.info(f"🎵 Music keyword: '{music_kw}' → song '{song_name}'")
            song_query = SONG_PRESETS.get(song_name, song_name)
            await _broadcast({"type": "thinking", "user": user_text})

            # Bài có choreography riêng → dùng play_choreography_with_music
            CHOREOGRAPHY_SONGS = {"sexy love", "bopeep"}

            # Bài cần nhảy thật sôi động (không choreography chi tiết)
            TET_HIGH_ENERGY_SONGS = {"tet_chuc_tet"}

            async def _music_task(q=song_query, s=song_name):
                url = await _download_youtube_audio(q)
                if url:
                    await _broadcast({
                        "type": "conversation", "user": user_text,
                        "bot": f"Nhảy bài {s} nào! 🎵💃",
                        "emotion": "dance", "actions": ["dance"], "source": source,
                    })
                    if s in CHOREOGRAPHY_SONGS:
                        log.info(f"🎭 Using full choreography for '{s}'")
                        await robot.play_choreography_with_music(url)
                    elif s in TET_HIGH_ENERGY_SONGS:
                        # Dùng danh sách dance nhiều và mạnh hơn cho bài chúc Tết
                        high_energy_dances = [
                            "dance_0001", "dance_0002", "dance_0003",
                            "dance_0004", "dance_0005", "dance_0006",
                            "dance_0007", "dance_0008", "dance_0009",
                            "dance_0012", "dance_0013", "dance_0014",
                            "dance_0015", "dance_0016", "dance_0017",
                            "dance_0018", "dance_0019", "dance_0020",
                            "dance_0021", "dance_0022", "dance_0023",
                        ]
                        log.info("💥 Using high-energy dance set for Tết song")
                        await robot.play_music_with_dance(url, high_energy_dances)
                    else:
                        await robot.play_music_with_dance(url)
                else:
                    await _broadcast({"type": "error", "message": "Không thể tải nhạc"})

            asyncio.create_task(_music_task())
            return {"type": "conversation", "user": user_text,
                    "bot": f"Đang tải bài {song_name}, chờ tí nhé!",
                    "emotion": "dance", "actions": ["dance"], "source": source}

    # ── Phát hiện keyword hành động trong câu người dùng ─────────────────────
    keyword_actions = _detect_action_keywords(user_text)
    if keyword_actions:
        # Thực hiện action NGAY (không đợi AI) — phản hồi tức thì
        async def _run_keyword_actions():
            for action_id in keyword_actions:
                await robot.play_action(action_id)
        asyncio.create_task(_run_keyword_actions())

    # ── Gọi AI ────────────────────────────────────────────────────────────────
    result     = await ai.chat(user_text)
    text       = result["text"]
    emotion    = result["emotion"]
    ai_actions = result.get("actions", [])
    log.info(f"AI [{emotion}] ai_actions={ai_actions}: {text}")

    # ── AI cũng có thể emit [ACTION:xxx] → chạy qua keyword map ──────────────
    if ai_actions and not keyword_actions:
        # Tạo text giả để detect keyword từ AI actions
        ai_action_text = " ".join(ai_actions)
        ai_keyword_actions = _detect_action_keywords(ai_action_text)
        if ai_keyword_actions:
            async def _run_ai_actions():
                for action_id in ai_keyword_actions:
                    await robot.play_action(action_id)
            asyncio.create_task(_run_ai_actions())
            asyncio.create_task(robot.speak_only(text))
        else:
            asyncio.create_task(robot.respond(text, emotion))
    elif keyword_actions:
        # Keyword đã bắt từ user input → chỉ TTS
        asyncio.create_task(robot.speak_only(text))
    else:
        asyncio.create_task(robot.respond(text, emotion))

    all_actions = keyword_actions + [a for a in ai_actions if a not in keyword_actions]

    # Broadcast kết quả tới tất cả app
    message = {
        "type":    "conversation",
        "user":    user_text,
        "bot":     text,
        "emotion": emotion,
        "actions": all_actions,
        "source":  source,
    }
    await _broadcast(message)
    return message


async def _on_robot_speech(text: str):
    """Callback khi robot microphone nhận diện được giọng nói."""
    await _process_message(text, source="robot")


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    ws_clients.add(websocket)
    client = websocket.client.host
    log.info(f"📱 App connected: {client}  (total: {len(ws_clients)})")

    # Gửi lịch sử chat + trạng thái cho client mới
    await websocket.send_text(json.dumps({
        "type":    "init",
        "history": ai.get_history(),
        "status": {
            "ai_ready":        ai.is_ready,
            "robot_connected": robot.is_connected,
        }
    }))

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                # Gửi ping để giữ kết nối
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
                continue

            data = json.loads(raw)
            if data.get("type") == "pong":
                continue   # ignore pong
            await _handle_ws_command(data, websocket)

    except WebSocketDisconnect:
        log.info(f"📱 App disconnected: {client}")
    except Exception as e:
        log.error(f"WebSocket error ({client}): {e}")
    finally:
        ws_clients.discard(websocket)


async def _handle_ws_command(data: dict, ws: WebSocket):
    cmd = data.get("type", "")

    # ── Chat: người dùng gõ text ──────────────────────────────────────────────
    if cmd == "chat":
        text = (data.get("text") or "").strip()
        if text:
            await _process_message(text, source="app")

    # ── Reset conversation ────────────────────────────────────────────────────
    elif cmd == "reset":
        ai.clear_history()
        asyncio.create_task(
            robot.respond("Được rồi! Chúng ta bắt đầu cuộc trò chuyện mới nhé!", "wave")
        )
        await ws.send_text(json.dumps({"type": "reset_ok"}))

    # ── Status query ──────────────────────────────────────────────────────────
    elif cmd == "status":
        await ws.send_text(json.dumps({
            "type":            "status",
            "ai_ready":        ai.is_ready,
            "robot_connected": robot.is_connected,
            "history_turns":   len(ai.get_history()) // 2,
        }))

    # ── Phát nhạc + nhảy ─────────────────────────────────────────────────────
    elif cmd == "play_music":
        song = data.get("song", "sexy love")
        song_query = SONG_PRESETS.get(song.lower(), song)
        await ws.send_text(json.dumps({"type": "thinking", "user": f"Đang tải bài: {song}…"}))
        url = await _download_youtube_audio(song_query)
        if url:
            _choreo_songs = {"sexy love", "bopeep"}
            if song.lower() in _choreo_songs:
                asyncio.create_task(robot.play_choreography_with_music(url))
            else:
                asyncio.create_task(robot.play_music_with_dance(url, data.get("dance_ids")))
            await ws.send_text(json.dumps({
                "type": "conversation", "bot": f"Nhảy bài {song} nào! 🎵",
                "emotion": "dance", "actions": ["dance"],
            }))
        else:
            await ws.send_text(json.dumps({"type": "error", "message": "Không thể tải nhạc"}))

    # ── Dừng nhạc/hành động ───────────────────────────────────────────────────
    elif cmd == "stop_music":
        await robot.stop_audio()
        await ws.send_text(json.dumps({"type": "status", "message": "Đã dừng nhạc"}))

    # ── Trực tiếp gửi lệnh robot (bypass AI) ─────────────────────────────────
    elif cmd == "robot_action":
        action = data.get("action")
        if action == "speak":
            await robot.speak(data.get("text", ""))
        elif action == "emotion":
            await robot.perform_emotion(data.get("emotion", "happy"))

    else:
        await ws.send_text(json.dumps({"type": "error", "message": f"Unknown command: {cmd}"}))


# ── Xiaozhi WebSocket (SelfHost cho Xiaozhi Android app) ───────────────────────

@app.websocket("/ws/xiaozhi")
async def websocket_xiaozhi(websocket: WebSocket):
    """
    Endpoint Xiaozhi protocol — Xiaozhi Android chọn SelfHost, nhập:
    ws://IP_SERVER:8000/ws/xiaozhi

    Yêu cầu: ffmpeg (ASR), OPENAI_API_KEY (Whisper ASR)
    """
    async def ai_chat(text: str):
        r = await _process_message(text, source="xiaozhi")
        return {"text": r.get("bot", ""), "emotion": r.get("emotion", "happy"), **r}

    async def robot_respond(text: str, emotion: str):
        await robot.respond(text, emotion)

    await handle_xiaozhi_websocket(websocket, ai_chat, robot_respond)


# ── REST API ──────────────────────────────────────────────────────────────────

@app.get("/status", summary="Server + robot + AI status")
async def get_status():
    return {
        "server":          "running",
        "uptime_seconds":  round(time.time() - start_time, 1),
        "ai_ready":        ai.is_ready,
        "ai_provider":     "gemini" if ai._ready else "not configured",
        "robot_connected": robot.is_connected,
        "active_clients":  len(ws_clients),
        "history_turns":   len(ai.get_history()) // 2,
    }


@app.get("/history", summary="Get conversation history")
async def get_history():
    return {"history": ai.get_history()}


class ChatRequest(BaseModel):
    text: str


@app.post("/chat", summary="Send message via REST (for testing)")
async def rest_chat(req: ChatRequest):
    if not req.text.strip():
        return JSONResponse(status_code=400, content={"error": "Text cannot be empty"})
    result = await _process_message(req.text.strip(), source="rest")
    return result


@app.post("/reset", summary="Reset conversation history")
async def reset_conversation():
    ai.clear_history()
    return {"status": "ok", "message": "Conversation reset"}


class PlayMusicRequest(BaseModel):
    song: str = "sexy love"   # tên bài hoặc query YouTube tự do
    dance_ids: list[str] | None = None


@app.post("/play_music", summary="Phát nhạc YouTube + robot nhảy đồng thời")
async def play_music_endpoint(req: PlayMusicRequest):
    song_query = SONG_PRESETS.get(req.song.lower(), req.song)
    await _broadcast({"type": "thinking", "user": f"Đang chuẩn bị bài: {req.song}…"})

    url = await _download_youtube_audio(song_query)
    if not url:
        return JSONResponse(status_code=500, content={"error": "Không thể tải nhạc"})

    await _broadcast({
        "type": "conversation",
        "user": req.song,
        "bot":  f"Nhảy bài {req.song} nào! 🎵",
        "emotion": "dance",
        "actions": ["dance"],
        "source": "music",
    })

    # Bài có choreography riêng thì dùng timed choreography, bài khác dùng random loop
    CHOREOGRAPHY_SONGS = {"sexy love", "bopeep"}
    if req.song.lower() in CHOREOGRAPHY_SONGS:
        asyncio.create_task(robot.play_choreography_with_music(url))
    else:
        asyncio.create_task(robot.play_music_with_dance(url, req.dance_ids))
    return {"status": "playing", "song": req.song, "url": url, "mode": "choreography" if req.song.lower() in CHOREOGRAPHY_SONGS else "random"}


# ── Broadcast helper ──────────────────────────────────────────────────────────

async def _broadcast(message: dict):
    """Gửi JSON message tới tất cả WebSocket client đang kết nối."""
    if not ws_clients:
        return
    payload = json.dumps(message, ensure_ascii=False)
    dead = set()
    for client in ws_clients:
        try:
            await client.send_text(payload)
        except Exception:
            dead.add(client)
    ws_clients.difference_update(dead)   # in-place, không trigger local-var bug


# ── Dev entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host=SERVER_HOST, port=SERVER_PORT, reload=True)
