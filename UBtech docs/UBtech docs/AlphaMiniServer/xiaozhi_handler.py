"""
xiaozhi_handler.py — Xử lý giao thức WebSocket Xiaozhi
Cho phép Xiaozhi Android app kết nối SelfHost tới Alpha Mini Server.

Giao thức:
- Client gửi hello → Server trả hello + session_id
- Client gửi Opus binary → Server ASR → trả {"type":"stt","text":"..."}
- Server gọi AI → TTS → gửi {"type":"tts","state":"start"}, Opus binary, {"type":"tts","state":"stop"}
"""

import asyncio
import io
import json
import logging
import uuid
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger("Xiaozhi")


# ── ASR (Speech-to-Text) ─────────────────────────────────────────────────────

async def _opus_to_wav(opus_bytes: bytes) -> bytes | None:
    """Chuyển Opus bytes sang WAV bytes (cần ffmpeg)."""
    import tempfile
    import subprocess
    try:
        with tempfile.NamedTemporaryFile(suffix=".opus", delete=False) as f:
            f.write(opus_bytes)
            opus_path = f.name
        wav_path = opus_path[:-5] + ".wav"
        try:
            # Thử ogg/opus trước, nếu lỗi thì thử raw opus
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", opus_path, "-f", "wav", wav_path],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                result = subprocess.run(
                    ["ffmpeg", "-y", "-f", "opus", "-ar", "16000", "-ac", "1", "-i", opus_path, "-f", "wav", wav_path],
                    capture_output=True,
                    timeout=10,
                )
            if result.returncode != 0:
                log.debug(f"ffmpeg stderr: {result.stderr.decode()[:200]}")
                return None
            with open(wav_path, "rb") as f:
                data = f.read()
            return data
        finally:
            Path(opus_path).unlink(missing_ok=True)
            Path(wav_path).unlink(missing_ok=True)
    except FileNotFoundError:
        log.warning("ffmpeg chưa cài: pip install ffmpeg-python hoặc cài ffmpeg vào PATH")
        return None
    except Exception as e:
        log.warning(f"Opus decode failed: {e}")
        return None


async def _transcribe_audio(wav_bytes: bytes) -> str | None:
    """Chuyển WAV sang text. Dùng OpenAI Whisper nếu có key."""
    import os
    api_key = os.getenv("OPENAI_API_KEY") or ""
    if not api_key or api_key.startswith("sk-proj-YOUR"):
        log.warning("OPENAI_API_KEY chưa cấu hình — bỏ qua ASR. Cấu hình để dùng giọng nói với Xiaozhi.")
        return None
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        buf = io.BytesIO(wav_bytes)
        buf.name = "audio.wav"
        resp = await client.audio.transcriptions.create(model="whisper-1", file=buf)
        return (resp.text or "").strip() or None
    except Exception as e:
        log.error(f"Whisper ASR error: {e}")
        return None


# ── TTS (Text-to-Speech) → Opus ─────────────────────────────────────────────

async def _tts_to_opus(text: str, sample_rate: int = 24000) -> bytes | None:
    """TTS text → Opus bytes cho Xiaozhi client."""
    try:
        import edge_tts
        from pydub import AudioSegment

        communicate = edge_tts.Communicate(text=text, voice="vi-VN-HoaiMyNeural")
        mp3_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_chunks.append(chunk["data"])

        if not mp3_chunks:
            return None

        mp3_bytes = b"".join(mp3_chunks)
        seg = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
        seg = seg.set_frame_rate(sample_rate).set_channels(1)
        out = io.BytesIO()
        seg.export(out, format="ogg", codec="libopus")
        return out.getvalue()
    except Exception as e:
        log.error(f"TTS to Opus error: {e}")
        return None


# ── Xiaozhi WebSocket handler ───────────────────────────────────────────────

async def handle_xiaozhi_websocket(
    websocket: WebSocket,
    ai_chat_func,
    robot_respond_func,
):
    """
    Xử lý kết nối WebSocket Xiaozhi.
    ai_chat_func: async (text: str) -> dict với keys: text, emotion, actions
    robot_respond_func: async (text: str, emotion: str) -> None
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())[:8]
    audio_buffer = bytearray()
    last_audio_time = 0.0
    BUFFER_TIMEOUT = 1.5  # giây chờ sau khi hết audio
    MIN_AUDIO_LEN = 1000  # tối thiểu bytes để ASR

    log.info(f"🎤 Xiaozhi client connected, session={session_id}")

    # Chờ hello từ client
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        msg = json.loads(raw)
        if msg.get("type") != "hello":
            log.warning(f"Expected hello, got: {msg.get('type')}")
            await websocket.close()
            return

        # Trả hello
        hello_reply = {
            "type": "hello",
            "transport": "websocket",
            "audio_params": {"sample_rate": 16000},
            "session_id": session_id,
        }
        await websocket.send_text(json.dumps(hello_reply))
        log.info("Xiaozhi hello handshake OK")

    except asyncio.TimeoutError:
        log.warning("Xiaozhi hello timeout")
        await websocket.close()
        return
    except Exception as e:
        log.error(f"Xiaozhi handshake error: {e}")
        await websocket.close()
        return

    # Loop xử lý message
    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive(), timeout=2.0)
            except asyncio.TimeoutError:
                # Kiểm tra buffer timeout — gửi ASR nếu đủ audio
                import time
                if audio_buffer and (time.time() - last_audio_time) > BUFFER_TIMEOUT:
                    opus_data = bytes(audio_buffer)
                    audio_buffer.clear()
                    if len(opus_data) >= MIN_AUDIO_LEN:
                        asyncio.create_task(_process_audio_and_reply(
                            opus_data, websocket, ai_chat_func, robot_respond_func
                        ))
                continue

            # Starlette receive() trả dict: {"type":"websocket.receive", "text":...} hoặc {"bytes":...}
            if "text" in msg:
                raw = msg.get("text", "{}")
                try:
                    data = json.loads(raw) if isinstance(raw, str) else raw
                    _type = data.get("type")
                    if _type == "listen" and data.get("state") == "stop":
                        if audio_buffer and len(audio_buffer) >= MIN_AUDIO_LEN:
                            opus_data = bytes(audio_buffer)
                            audio_buffer.clear()
                            asyncio.create_task(_process_audio_and_reply(
                                opus_data, websocket, ai_chat_func, robot_respond_func
                            ))
                    elif _type == "abort":
                        audio_buffer.clear()
                except json.JSONDecodeError:
                    pass
            elif "bytes" in msg and msg["bytes"]:
                audio_buffer.extend(msg["bytes"])
                import time
                last_audio_time = time.time()

    except WebSocketDisconnect:
        log.info(f"Xiaozhi client disconnected: {session_id}")
    except Exception as e:
        log.error(f"Xiaozhi handler error: {e}")


async def _process_audio_and_reply(
    opus_data: bytes,
    websocket: WebSocket,
    ai_chat_func,
    robot_respond_func,
):
    """ASR → AI → TTS → gửi về client + robot."""
    wav = await _opus_to_wav(opus_data)
    if not wav:
        return

    text = await _transcribe_audio(wav)
    if not text:
        log.info("ASR: không nhận diện được (hoặc chưa cấu hình OPENAI_API_KEY)")
        return

    log.info(f"Xiaozhi STT: {text}")

    # Gửi stt cho client
    await websocket.send_text(json.dumps({"type": "stt", "text": text}))

    # Gọi AI
    result = await ai_chat_func(text)
    bot_text = result.get("text") or result.get("bot", "")
    emotion = result.get("emotion", "happy")

    if not bot_text:
        return

    # Gửi emotion
    await websocket.send_text(json.dumps({"type": "llm", "emotion": emotion}))

    # TTS → Opus → gửi cho client
    await websocket.send_text(json.dumps({"type": "tts", "state": "start"}))
    opus_audio = await _tts_to_opus(bot_text)
    if opus_audio:
        await websocket.send_bytes(opus_audio)
    await websocket.send_text(json.dumps({"type": "tts", "state": "stop"}))

    # Robot phát + hành động
    await robot_respond_func(bot_text, emotion)
