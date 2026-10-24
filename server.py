import asyncio
import base64
import hashlib
import json
import os
import logging
import re
import subprocess
import time
import unicodedata
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import ws_mini_compat

from google import genai
from google.genai import types
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import config

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)
ws_mini_compat.apply_mini_websocket_compat()

# Uptime cho GET /connect/diagnose (monotonic — không lùi khi đổi giờ hệ thống).
_SERVER_MONO_START = time.monotonic()

# Bộ nhớ cache MP3 cho TTS HTTP (robot tải qua LAN)
_TTS_CACHE_DIR = Path(__file__).resolve().parent / "tts_cache"
_ROBOT_MUSIC_DIR = Path(__file__).resolve().parent / "robot_music"


def _ensure_tts_cache_dir() -> None:
    _TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)


async def _unlink_later(path: Path, delay: float = 600.0) -> None:
    await asyncio.sleep(delay)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


async def _synthesize_fpt_tts_bytes(text: str) -> bytes:
    """FPT.AI v5: POST text → JSON có link async; poll tải MP3 (file có thể chưa sẵn sàng ngay)."""
    import time

    import aiohttp

    key = (config.FPT_AI_TTS_API_KEY or "").strip()
    if not key:
        raise RuntimeError("Chưa cấu hình FPT_AI_TTS_API_KEY (ROBOT_TTS_HTTP_ENGINE=fpt)")
    api_url = (config.FPT_AI_TTS_URL or "https://api.fpt.ai/hmi/tts/v5").strip()
    voice = (config.FPT_AI_TTS_VOICE or "minhquang").strip()
    speed = str((config.FPT_AI_TTS_SPEED or "0").strip())
    fmt = (config.FPT_AI_TTS_FORMAT or "mp3").strip().lower()
    hname = (config.FPT_AI_TTS_API_HEADER or "api-key").strip()

    t = (text or "").strip()
    if len(t) < 3:
        t = (t + "...")[:5000].ljust(3, ".")
    if len(t) > 5000:
        t = t[:5000]

    headers = {
        hname: key,
        "voice": voice,
        "speed": speed,
        "format": fmt,
        "Cache-Control": "no-cache",
        "Content-Type": "text/plain; charset=utf-8",
    }

    timeout = aiohttp.ClientTimeout(
        total=None,
        sock_connect=30,
        sock_read=max(60.0, float(config.FPT_AI_TTS_POLL_TIMEOUT_SEC) + 30.0),
    )
    poll_deadline = time.monotonic() + float(config.FPT_AI_TTS_POLL_TIMEOUT_SEC)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            api_url,
            data=t.encode("utf-8"),
            headers=headers,
        ) as resp:
            raw = await resp.read()
            if resp.status != 200:
                raise RuntimeError(f"FPT TTS HTTP {resp.status}: {raw[:600]!r}")
            try:
                j = json.loads(raw.decode("utf-8", errors="replace"))
            except json.JSONDecodeError as e:
                raise RuntimeError(f"FPT TTS không phải JSON: {raw[:400]!r}") from e

        if j.get("error") != 0:
            raise RuntimeError(f"FPT TTS lỗi API: {j!r}")
        audio_url = j.get("async")
        if not audio_url or not isinstance(audio_url, str):
            raise RuntimeError(f"FPT TTS thiếu async URL: {j!r}")

        log.info("FPT TTS request_id=%s, polling %s", j.get("request_id"), audio_url[:80])

        delay = 1.5
        while time.monotonic() < poll_deadline:
            async with session.get(audio_url) as aresp:
                body = await aresp.read()
                if aresp.status == 200 and len(body) > 256:
                    return body
            await asyncio.sleep(delay)

        raise RuntimeError("FPT TTS: hết thời gian chờ file âm thanh (thử tăng FPT_AI_TTS_POLL_TIMEOUT_SEC)")


async def synthesize_tts_mp3_to_cache(text: str) -> Path:
    """Tạo file .mp3 trong tts_cache; caller có thể schedule xóa sau khi robot đã tải."""
    _ensure_tts_cache_dir()
    t = (text or "").strip()
    if not t:
        raise ValueError("empty TTS text")
    out = _TTS_CACHE_DIR / f"{uuid.uuid4().hex}.mp3"
    engine = (config.ROBOT_TTS_HTTP_ENGINE or "edge").strip().lower()

    if engine == "fpt":
        data = await _synthesize_fpt_tts_bytes(t)
        out.write_bytes(data)
        return out

    if engine == "google":
        try:
            from google.cloud import texttospeech
        except ImportError as e:
            raise RuntimeError(
                "google-cloud-texttospeech chưa cài: pip install google-cloud-texttospeech"
            ) from e

        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=t)
        lang = (config.GOOGLE_TTS_LANGUAGE_CODE or "vi-VN").strip()
        voice_name = (config.GOOGLE_TTS_VOICE_NAME or "").strip()
        if voice_name:
            voice = texttospeech.VoiceSelectionParams(language_code=lang, name=voice_name)
        else:
            voice = texttospeech.VoiceSelectionParams(language_code=lang)
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=max(0.25, min(4.0, float(config.GOOGLE_TTS_SPEAKING_RATE or 1.0))),
        )

        def _syn():
            return client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )

        response = await asyncio.to_thread(_syn)
        out.write_bytes(response.audio_content)
    else:
        import edge_tts

        voice = (config.EDGE_TTS_VOICE or "vi-VN-HoaiMyNeural").strip()
        rate = (config.EDGE_TTS_RATE or "+0%").strip()
        pitch = (config.EDGE_TTS_PITCH or "+0Hz").strip()
        vol = (config.EDGE_TTS_VOLUME or "+0%").strip()
        communicate = edge_tts.Communicate(t, voice, rate=rate, pitch=pitch, volume=vol)
        await communicate.save(str(out))

    return out


def normalize_text(text: str) -> str:
    """Chữ thường, bỏ dấu, đ→d; gộp khoảng trắng; ký tự không phải chữ/số → khoảng (đứng, lên → dung len)."""
    text = text.lower().strip()
    text = text.replace("đ", "d")
    text = "".join(
        ch for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _normalize_openclaw_pending_text(text: str) -> str:
    """
    OpenClaw tool `write` đôi khi ghi cả câu xác nhận kiểu:
    «Đã nhận lệnh 'nói cảm ơn bạn'. Robot sẽ…» thay vì chỉ lệnh user.
    Trích phần trong ngoặc sau «nhận lệnh» để keyword / speak_text khớp đúng.
    """
    t = (text or "").strip()
    if len(t) < 15:
        return t
    # Có dấu: ... lệnh '...' hoặc '...'
    m = re.search(
        r"(?is)nhận\s+lệnh\s*[\u2018'']([^\u2019']{1,800})[\u2019']",
        t,
    )
    if m:
        inner = (m.group(1) or "").strip()
        if inner and len(inner) < len(t):
            return inner
    # Không dấu / ASCII
    m = re.search(r"(?is)nhan\s+lenh\s*['\"]([^'\"]{1,800})['\"]", t)
    if m:
        inner = (m.group(1) or "").strip()
        if inner and len(inner) < len(t):
            return inner
    # Nhiều prompt xác nhận kiểu:
    # "Đã bảo robot nói xin chào rồi", "Mình đã gửi lệnh cho robot nói ..."
    # -> trích phần lệnh sau "robot"/"cho robot" để backend thực thi đúng thay vì coi là câu xác nhận.
    confirm_patterns = (
        r"(?is)^(?:mình|minh|toi|tôi)?\s*đã\s+(?:bảo|bao|gửi\s+lệnh|gui lenh)(?:\s+cho)?\s+robot\s+(.+)$",
        r"(?is)^da\s+(?:bao|gui\s+lenh)(?:\s+cho)?\s+robot\s+(.+)$",
    )
    for pat in confirm_patterns:
        m = re.search(pat, t)
        if not m:
            continue
        inner = (m.group(1) or "").strip()
        # Bỏ hậu tố xác nhận thường gặp ở cuối câu.
        inner = re.sub(r"(?is)\s*(rồi|roi|rồi nhé|roi nhe|nhé|nhe)\s*[.!…]*\s*$", "", inner).strip()
        # Chuẩn hóa dấu kết thúc để intent parser dễ nhận.
        inner = inner.rstrip(".!… ").strip()
        if inner and len(inner) < len(t):
            return inner
    return t


def _decode_openclaw_pending_chat(data: bytes) -> str:
    """
    OpenClaw có thể ghi pending file theo UTF-8 hoặc UTF-16 (tuỳ máy/công cụ viết file).
    Ta thử nhiều encoding rồi chọn bản decode ít ký tự thay thế nhất để tránh hỏng tiếng Việt.
    """
    if not data:
        return ""

    # (encoding, weight) — ưu tiên UTF-8 trước, sau đó mới UTF-16 tuỳ endianness.
    encs = [
        ("utf-8-sig", 1.0),
        ("utf-8", 1.0),
        ("utf-16le", 0.9),
        ("utf-16be", 0.9),
    ]

    best_txt = ""
    best_score = float("-inf")

    for enc, w in encs:
        try:
            txt = data.decode(enc, errors="replace")
        except Exception:
            continue

        replacement_count = txt.count("�")
        # Tính số ký tự chữ/số để biết decode có “ra chữ” hay không.
        letters = sum(
            1
            for ch in txt
            if unicodedata.category(ch).startswith(("L", "N"))
        )
        # Chọn decode có ít replacement nhất, đồng thời nhiều chữ hơn.
        score = (letters * w) - (replacement_count * 200.0)
        if score > best_score:
            best_score = score
            best_txt = txt

    return best_txt.lstrip("\ufeff").strip()


def _write_openclaw_last_reply(reply: str) -> None:
    """Ghi phản hồi cuối để OpenClaw/skill có thể đọc lại; lỗi ghi file chỉ log warning."""
    try:
        p = Path(config.OPENCLAW_LAST_REPLY_PATH)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text((reply or "").strip(), encoding="utf-8")
    except Exception as e:
        log.warning("write OPENCLAW_LAST_REPLY_PATH failed: %s", e)


def _greet_speech_from_text(text: str) -> str | None:
    """
    Nếu user yêu cầu kiểu: "hãy nói xin chào đi" → map thành câu nói ngắn cho robot.
    Lưu ý: normalize_text sẽ bỏ dấu, nên ta chỉ cần kiểm tra theo dạng không dấu.
    """
    if not text:
        return None
    t = normalize_text(text)
    if "xin chao" in t:
        # Khong doc "xin chao di" (tu "di" o cuoi cau lenh) — chi mot cau chao ngan.
        return "Xin chao!"
    return None


_MAX_SPEAK_PHRASE_LEN = 500


def _strip_speak_command_suffix(phrase: str) -> str:
    """Bo 'đi / nhé / nào' o cuoi lenh noi."""
    s = (phrase or "").strip()
    s = re.sub(r"(?is)\s+(đi|di|nhé|nhe|nào|nao|nhe)([\s.!?…]*)$", "", s)
    return s.strip()


def _speak_phrase_negated_before(text: str, noi_start: int) -> bool:
    """Tu 'noi' sau 'dung/khong...' (gan truoc) -> khong lay cum."""
    pre = text[: max(0, noi_start)].rstrip()
    if len(pre) < 2:
        return False
    return bool(re.search(r"(?is)(đừng|dung|không|chớ|chua|đừng)\s*$", pre))


def _extract_speak_phrase_after_noi(text: str) -> str | None:
    """
    Cum can robot noi sau tu 'nói' / say / speak (uu tien tieng Viet).
    Vi du: 'hay noi cam on ban' -> 'cam on ban'; 'say hello there' -> 'hello there'.
    """
    raw = (text or "").strip()
    if not raw:
        return None

    m = re.match(r"(?is)^(?:please\s+)?(?:say|speak)\s+(.+)$", raw)
    if m:
        p = _strip_speak_command_suffix(m.group(1))
        if p and "http" not in p.casefold():
            return p[:_MAX_SPEAK_PHRASE_LEN]

    m = re.match(
        r"(?is)^(?:hãy\s+|hay\s+)?(?:làm\s+ơn\s+|lam\s+on\s+)?(?:nói\s+giúp\s+|noi\s+giup\s+)?nói\s+(.+)$",
        raw,
    )
    if m:
        p = _strip_speak_command_suffix(m.group(1))
        if p and "http" not in p.casefold() and "www." not in p.casefold():
            return p[:_MAX_SPEAK_PHRASE_LEN]

    for m in reversed(list(re.finditer(r"(?is)\bnói\s+", raw))):
        if _speak_phrase_negated_before(raw, m.start()):
            continue
        p = _strip_speak_command_suffix(raw[m.end() :])
        if not p or "http" in p.casefold():
            continue
        # "nổi tiếng"/"noi tieng" là tính từ (famous), không phải lệnh robot nói.
        if p.casefold().startswith(("tiếng", "tieng")):
            continue
        return p[:_MAX_SPEAK_PHRASE_LEN]

    # Da normalize (khong dau): "noi cam on"
    raw2 = raw
    m = re.match(
        r"(?is)^(?:hay\s+)?(?:lam\s+on\s+)?(?:noi\s+giup\s+)?noi\s+(.+)$",
        raw2,
    )
    if m:
        p = _strip_speak_command_suffix(m.group(1))
        if p and "http" not in p.casefold():
            return p[:_MAX_SPEAK_PHRASE_LEN]
    for m in reversed(list(re.finditer(r"(?is)\bnoi\s+", raw2))):
        if _speak_phrase_negated_before(raw2, m.start()):
            continue
        p = _strip_speak_command_suffix(raw2[m.end() :])
        if not p or "http" in p.casefold():
            continue
        if p.casefold().startswith("tieng"):
            continue
        return p[:_MAX_SPEAK_PHRASE_LEN]
    return None


def _user_wants_silence(text: str) -> bool:
    """Người dùng muốn không đọc / im — ưu tiên hơn yêu cầu nói."""
    t = normalize_text(text)
    return _kw_any(
        t,
        (
            "dung doc",
            "dung noi",
            "dung loa",
            "thoi doc",
            "thoi noi",
            "im lang",
            "yen lang",
            "tat tieng",
            "khong doc",
            "khong noi",
            "khong can doc",
            "chi can text",
            "chi viet",
            "silent",
            "mute",
            "no tts",
            "tts off",
            "dont read aloud",
            "do not speak",
        ),
    )


def _user_wants_spoken_reply(text: str) -> bool:
    """Bật TTS kể cả khi client gửi speak=false (vd. OpenClaw) nếu câu có ý muốn nghe loa."""
    if not (text or "").strip():
        return False
    t = normalize_text(text)
    raw = (text or "").casefold()
    if _user_wants_silence(text):
        return False
    if _kw_any(
        t,
        (
            "doc cho toi nghe",
            "doc cho minh nghe",
            "doc cho em nghe",
            "doc cho anh nghe",
            "doc cho chi nghe",
            "doc di",
            "doc ra",
            "doc to len",
            "doc loi",
            "hay doc",
            "doc bang loa",
            "cho toi nghe",
            "cho minh nghe",
            "minh muon nghe",
            "toi muon nghe",
            "muon nghe",
            "nghe robot noi",
            "noi di",
            "noi cho toi nghe",
            "noi to len",
            "noi bang loa",
            "noi bang giong",
            "ke cho toi nghe",
            "ke cho minh nghe",
            "ke cho em nghe",
            "ke di",
            "hay ke",
            "ke chuyen",
            "ke ten",
            "dung giong noi",
            "phat thanh",
            "doc thanh",
            "bang am thanh",
            "bang tieng noi",
            "read aloud",
            "read it out",
            "say it out loud",
            "speak out",
            "speak it",
            "say aloud",
            "voice output",
            "use your voice",
            "tts",
            "text to speech",
            "bat loa",
            "mo loa",
            "phat qua loa",
        ),
    ):
        return True
    # Một số cụm nhạy cảm với normalize / từ tách
    if any(
        x in raw
        for x in (
            "đọc cho",
            "đọc đi",
            "nói đi",
            "nói cho",
            "đọc to",
            "nói to",
            "kể cho",
            "kể đi",
            "hãy kể",
            "kể tên",
            "kể chuyện",
            "loa đi",
            "nói xin chào",
            "hãy nói",
        )
    ):
        return True
    # "noi xin chao di" — khong co cum lien "noi di" nhung ro rang muon robot noi.
    if "noi" in t.split() and "xin chao" in t:
        return True
    return False


def _action_info_items_to_json(items) -> list[dict]:
    """SDK trả repeated ActionInfoResponse (protobuf) — FastAPI cần dict."""
    out: list[dict] = []
    for item in items or []:
        if isinstance(item, dict):
            out.append(item)
            continue
        try:
            from google.protobuf.json_format import MessageToDict

            if hasattr(item, "DESCRIPTOR"):
                out.append(MessageToDict(item, preserving_proto_field_name=True))
                continue
        except Exception:
            pass
        out.append({
            "id": getattr(item, "id", None) or "",
            "cnName": getattr(item, "cnName", None) or "",
            "enName": getattr(item, "enName", None) or "",
            "type": int(getattr(item, "type", 0) or 0),
        })
    return out


async def _download_robot_camera_image_bytes(robot_ip: str, pic_path: str) -> tuple[bytes | None, list[str]]:
    """
    Tải file ảnh từ robot sau take_picture (picPath trên máy robot).
    Thử ROBOT_IMAGE_URL_TEMPLATE rồi http://IP:port + path (ROBOT_FILE_HTTP_PORTS).
    """
    from urllib.parse import quote

    import aiohttp

    tried: list[str] = []
    if not pic_path or not robot_ip:
        log.warning("📸 download: thiếu pic_path hoặc robot_ip")
        return None, tried

    log.info("📸 download: bắt đầu robot_ip=%s picPath=%r", robot_ip, pic_path)

    paths: list[str] = [pic_path]
    if not pic_path.startswith("/"):
        paths.append("/" + pic_path)
    seen: set[str] = set()
    uniq_paths: list[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            uniq_paths.append(p)

    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tpl = (getattr(config, "ROBOT_IMAGE_URL_TEMPLATE", "") or "").strip()
        if tpl:
            for p in uniq_paths:
                q = quote(p, safe="/")
                try:
                    url = tpl.format(ip=robot_ip, path=q, raw_path=p)
                except (KeyError, IndexError):
                    url = tpl.replace("{ip}", robot_ip).replace("{path}", q).replace("{raw_path}", p)
                tried.append(url)
                try:
                    t_dl = time.monotonic()
                    async with session.get(url) as r:
                        dt = time.monotonic() - t_dl
                        if r.status == 200:
                            data = await r.read()
                            if len(data) > 64:
                                log.info(
                                    "📸 download: OK %s bytes từ %s (%.2fs)",
                                    len(data),
                                    url,
                                    dt,
                                )
                                return data, tried
                        log.info("📸 download: %s -> HTTP %s (%.2fs)", url, r.status, dt)
                except Exception as ex:
                    log.info("📸 download: %s -> lỗi %s", url, ex)

        ports_raw = (getattr(config, "ROBOT_FILE_HTTP_PORTS", "8080,8888,80") or "8080").replace(" ", "")
        for port in ports_raw.split(","):
            ps = port.strip()
            if not ps.isdigit():
                continue
            for p in uniq_paths:
                ep = quote(p, safe="/")
                url = f"http://{robot_ip}:{ps}{ep}"
                if url in tried:
                    continue
                tried.append(url)
                try:
                    t_dl = time.monotonic()
                    async with session.get(url) as r:
                        dt = time.monotonic() - t_dl
                        if r.status == 200:
                            data = await r.read()
                            if len(data) > 64:
                                log.info(
                                    "📸 download: OK %s bytes từ %s (%.2fs)",
                                    len(data),
                                    url,
                                    dt,
                                )
                                return data, tried
                        log.info("📸 download: %s -> HTTP %s (%.2fs)", url, r.status, dt)
                except Exception as ex:
                    log.info("📸 download: %s -> lỗi %s", url, ex)

    log.warning("📸 download: hết URL, không tải được (%s URL đã thử)", len(tried))
    return None, tried


def _extract_sdk_direct_image_bytes_from_take_picture_resp(resp: object) -> bytes | None:
    """
    Một số bản SDK/firmware trả dữ liệu ảnh trong response TakePicture (không cần HTTP tải picPath).
    Trả bytes hoặc None nếu không có field hợp lệ.
    """
    if resp is None:
        return None

    def _from_obj(obj: object) -> bytes | None:
        for attr_name in (
            "data",
            "pictureData",
            "picture_data",
            "content",
            "picData",
            "imageData",
            "image_data",
            "fileData",
            "bytes_data",
        ):
            data = getattr(obj, attr_name, None)
            if data is None:
                continue
            if isinstance(data, (bytes, bytearray)) and len(data) > 100:
                return bytes(data)
            if isinstance(data, str) and len(data) > 100:
                try:
                    decoded = base64.b64decode(data, validate=False)
                    if len(decoded) > 100:
                        return decoded
                except Exception:
                    pass
        if isinstance(obj, dict):
            for k in ("data", "pictureData", "picture_data", "content", "picData"):
                v = obj.get(k)
                if isinstance(v, (bytes, bytearray)) and len(v) > 100:
                    return bytes(v)
                if isinstance(v, str) and len(v) > 100:
                    try:
                        decoded = base64.b64decode(v, validate=False)
                        if len(decoded) > 100:
                            return decoded
                    except Exception:
                        pass
        return None

    direct = _from_obj(resp)
    if direct:
        return direct
    nested = getattr(resp, "response", None) or getattr(resp, "dataInfo", None) or getattr(resp, "info", None)
    if nested is not None and nested is not resp:
        return _from_obj(nested)
    return None


def _no_picture_http_detail(err: dict | None) -> str:
    """Thông báo HTTP cho take_picture thất bại (isSuccess/picPath/code từ firmware)."""
    if not err:
        return "Robot không chụp được."
    code = err.get("code")
    base = (
        f"Robot không chụp được (isSuccess={err.get('isSuccess')}, code={code}, "
        f"picPath={err.get('picPath')!r}"
    )
    if err.get("findface"):
        base += ", mode=FINDFACE"
    base += ")."
    if code == -2:
        base += (
            " Mã -2: firmware từ chối chụp (robot chưa sẵn sàng hoặc chưa vào đúng chế độ lập trình). "
            "Server đã có thể gọi enter_program() rồi chụp lại một lần (ROBOT_TAKE_PICTURE_RETRY_ENTER_PROGRAM). "
            "Gợi ý: đợi vài giây sau khi bật; thử ROBOT_TYPE=edu nếu là bản quốc tế; cập nhật firmware; "
            "nếu log khởi động báo enter_program không Success, lệnh chụp có thể luôn bị -2."
        )
    return base


async def _ensure_robot_for_camera() -> None:
    """WS đứt / chưa connect lần đầu → thử reconnect; nếu vẫn chưa có client thì connect_robot()."""
    if not getattr(config, "ROBOT_ENABLED", False):
        return
    await reconnect_robot_if_ws_dead()
    if robot is None:
        await connect_robot()


async def _robot_capture_image_bytes() -> tuple[bytes | None, dict | None]:
    """
    Một lần chụp ảnh robot: ưu tiên bytes trong response SDK (nếu có), sau đó HTTP tải picPath (fallback).
    Thành công: (bytes, None). Lỗi: (None, {"kind": "robot_offline"|...}).
    """
    img_mode = (getattr(config, "ROBOT_IMAGE_FETCH_MODE", "auto") or "auto").strip().lower()
    if img_mode not in ("auto", "sdk_only", "http_only"):
        img_mode = "auto"
    log.info("📸 capture: bắt đầu (mode=%s: SDK response bytes trước, rồi HTTP nếu auto/http_only)", img_mode)
    await _ensure_robot_for_camera()
    if not getattr(config, "ROBOT_ENABLED", False):
        log.info("📸 capture: dừng — ROBOT_ENABLED=false")
        return None, {"kind": "robot_disabled"}
    if not robot or not getattr(robot, "connected", False):
        log.info("📸 capture: dừng — robot_offline")
        return None, {"kind": "robot_offline"}

    from mini import MiniApiResultType, TakePictureType, mini_sdk
    from mini.apis.api_sence import TakePicture

    global _TAKE_PICTURE_ENTER_PROGRAM_RETRIED_THIS_SESSION

    async def _snap(use_findface: bool) -> tuple[bytes | None, dict | None]:
        tp = TakePictureType.FINDFACE if use_findface else TakePictureType.IMMEDIATELY
        snap_label = "FINDFACE" if use_findface else "IMMEDIATELY"
        log.info("📸 capture: gọi TakePicture.execute() mode=%s …", snap_label)
        t_sdk = time.monotonic()
        result_type, resp = await TakePicture(take_picture_type=tp).execute()
        dt_sdk = time.monotonic() - t_sdk
        log.info(
            "📸 capture: SDK trả sau %.2fs — result_type=%s",
            dt_sdk,
            getattr(result_type, "name", str(result_type)),
        )
        if result_type != MiniApiResultType.Success or resp is None:
            log.warning("📸 capture: sdk_transport result_type=%s resp=%s", result_type, resp)
            return None, {
                "kind": "sdk_transport",
                "resultType": getattr(result_type, "name", str(result_type)),
            }
        ok = bool(getattr(resp, "isSuccess", False))
        pic_path = (getattr(resp, "picPath", None) or "").strip()
        code = getattr(resp, "code", None)
        log.info(
            "📸 capture: SDK body isSuccess=%s code=%s picPath=%r",
            ok,
            code,
            pic_path,
        )
        if img_mode in ("auto", "sdk_only"):
            direct = _extract_sdk_direct_image_bytes_from_take_picture_resp(resp)
            if direct:
                log.info("📸 capture: hoàn tất OK (SDK direct, %d bytes)", len(direct))
                return direct, None

        if not ok or not pic_path:
            return None, {
                "kind": "no_picture",
                "isSuccess": ok,
                "code": code,
                "picPath": pic_path,
                "findface": use_findface,
            }
        if img_mode == "sdk_only":
            log.warning("📸 capture: sdk_only — có picPath nhưng response không chứa bytes ảnh")
            return None, {
                "kind": "sdk_no_data",
                "picPath": pic_path,
                "code": code,
                "message": (
                    "SDK chụp OK (có picPath) nhưng response không chứa bytes ảnh — firmware/SDK không trả "
                    "binary qua WebSocket. Thử: pip install -U alphamini; hoặc ROBOT_IMAGE_FETCH_MODE=auto; "
                    "hoặc cấu hình ROBOT_IMAGE_URL_TEMPLATE / ROBOT_FILE_HTTP_PORTS (HTTP file server)."
                ),
            }
        log.info("📸 capture: tải ảnh HTTP từ robot (picPath đã có, mode=%s)", img_mode)
        raw_img, tried = await _download_robot_camera_image_bytes(robot.ip, pic_path)
        if not raw_img:
            log.warning(
                "📸 capture: download_failed picPath=%r urls_tried=%s",
                pic_path,
                len(tried),
            )
            return None, {
                "kind": "download_failed",
                "picPath": pic_path,
                "urls_tried": tried,
                "message": (
                    "SDK chụp OK nhưng không tải được ảnh qua HTTP và (với mode=auto) response không có bytes trực tiếp. "
                    "Firmware Alpha Mini thường không mở HTTP file server trên 8080/8888/80. "
                    "Gợi ý: (1) pip install -U alphamini nếu SDK mới trả ảnh trong response; "
                    "(2) .env ROBOT_IMAGE_URL_TEMPLATE=http://{ip}:<port>{path} khớp firmware; "
                    "(3) PowerShell: .\\diagnose-robot-http.ps1; "
                    "(4) Test-NetConnection <ROBOT_IP> -Port 8080"
                ),
            }
        log.info("📸 capture: xong — %s bytes JPEG", len(raw_img))
        return raw_img, None


    async with _robot_action_lock:
        log.info("📸 capture: đã vào _robot_action_lock")
        try:
            raw_img, err = await _snap(False)
        except Exception as e:
            log.exception("TakePicture IMMEDIATELY")
            return None, {"kind": "sdk_error", "message": str(e)}

        if (
            err
            and err.get("kind") == "no_picture"
            and err.get("code") == -2
            and getattr(config, "ROBOT_TAKE_PICTURE_RETRY_ENTER_PROGRAM", True)
            and not _TAKE_PICTURE_ENTER_PROGRAM_RETRIED_THIS_SESSION
        ):
            _TAKE_PICTURE_ENTER_PROGRAM_RETRIED_THIS_SESSION = True
            log.warning(
                "take_picture code=-2 — gọi enter_program() rồi chụp lại (một lần mỗi phiên kết nối)"
            )
            try:
                await mini_sdk.enter_program()
            except Exception as ee:
                log.warning("enter_program trước khi chụp lại: %s", ee)
            try:
                raw_img, err = await _snap(False)
            except Exception as e:
                log.exception("TakePicture IMMEDIATELY (sau enter_program)")
                return None, {"kind": "sdk_error", "message": str(e)}

        if (
            raw_img is None
            and err
            and err.get("kind") == "no_picture"
            and getattr(config, "ROBOT_TAKE_PICTURE_TRY_FINDFACE", False)
        ):
            log.info("take_picture: thử FINDFACE (cần mặt trước camera)")
            try:
                raw_img, err = await _snap(True)
            except Exception as e:
                log.exception("TakePicture FINDFACE")
                return None, {"kind": "sdk_error", "message": str(e)}

        if err and err.get("kind") == "sdk_transport":
            log.warning("📸 capture: sdk_transport — %s", err)
            return None, err

    if raw_img:
        log.info("📸 capture: hoàn tất OK (%s bytes)", len(raw_img))
    else:
        log.warning("📸 capture: hoàn tất lỗi err=%s", err)
    return raw_img, err


def _decode_qr_codes_from_image_bytes(image_bytes: bytes) -> list[dict]:
    """
    Decode QR content from JPEG/PNG bytes using OpenCV QRCodeDetector.
    Returns list[{text, format}] (empty list if nothing found).
    """
    if not image_bytes:
        return []
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception as e:
        log.warning("QR decode deps missing: %s", e)
        return []

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        return []

    detector = cv2.QRCodeDetector()
    codes: list[dict] = []
    try:
        ok, decoded_info, _points, _ = detector.detectAndDecodeMulti(frame)
        if ok and decoded_info:
            for txt in decoded_info:
                t = (txt or "").strip()
                if t:
                    codes.append({"text": t, "format": "QR_CODE"})
    except Exception:
        pass

    if not codes:
        try:
            txt, _points, _ = detector.detectAndDecode(frame)
            t = (txt or "").strip()
            if t:
                codes.append({"text": t, "format": "QR_CODE"})
        except Exception:
            pass
    return codes


def build_quick_action_reply(text_norm: str, raw_text: str = "") -> str:
    if _wants_o_i_i_choreography(text_norm):
        if _o_i_i_with_na_na_backing(text_norm):
            return "OK, Alpha Mini dang mo bai O I I voi nhac na na na na!"
        return "OK, Alpha Mini dang mo bai O I I!"
    act = _classify_keyword_action(text_norm, raw_text or text_norm)
    if act == "dance":
        if _martial_intent_keywords_norm(text_norm):
            return "OK, Alpha Mini dang mua vo!"
        return "OK, Alpha Mini dang nhay ngay day!"
    if act == "turn_right":
        return "OK, Alpha Mini dang quay sang phai."
    if act == "turn_left":
        return "OK, Alpha Mini dang quay sang trai."
    if act == "walk_forward":
        return "OK, Alpha Mini dang di toi."
    if act == "stand":
        return "OK, Alpha Mini dang dung day."
    if act == "sit_down":
        return "OK, Alpha Mini dang ngoi xuong."
    if act == "sit_then_stand":
        return "OK, Alpha Mini se ngoi roi dung day."
    if act == "stop":
        return "OK, Alpha Mini dang dung lai."
    if act == "greet":
        return "Xin chao! Alpha Mini dang chao ban."
    if act == "speak_text":
        p = _extract_speak_phrase_after_noi(raw_text or text_norm)
        if p:
            short = p if len(p) <= 100 else p[:97] + "..."
            return f"OK, Alpha Mini se noi: {short}"
        return "OK, Alpha Mini se noi theo yeu cau."
    return "Da nhan lenh, Alpha Mini dang thuc hien."


def _martial_intent_keywords_norm(t: str) -> bool:
    """Câu kiểu múa võ / kung fu (sau normalize_text)."""
    return _kw_any(
        t,
        (
            "mua vo",
            "vo thuat",
            "tap vo",
            "luyen vo",
            "dien vo",
            "kung fu",
            "kungfu",
            "wushu",
            "martial art",
            "martial arts",
            "tai chi",
            "taichi",
            "shaolin",
            "karate",
        ),
    )


def resolve_behavior_from_message(text_norm: str) -> str | None:
    """Tìm behavior theo alias trong câu (alias .env + cụm bài cố định)."""
    if _martial_intent_keywords_norm(text_norm) and getattr(config, "ROBOT_MARTIAL_BEHAVIOR", "").strip():
        return config.ROBOT_MARTIAL_BEHAVIOR.strip()
    # Cụm sau normalize: "nà ná na na" → "na na na na"; "anh độ mixi" → "anh do mixi"
    if "na na na na" in text_norm or "na na na" in text_norm:
        if config.ROBOT_DANCE_NA_NA_BEHAVIOR:
            return config.ROBOT_DANCE_NA_NA_BEHAVIOR
    if "anh do mixi" in text_norm or "do mixi" in text_norm:
        if config.ROBOT_DANCE_MIXI_BEHAVIOR:
            return config.ROBOT_DANCE_MIXI_BEHAVIOR
    for alias, behavior_id in config.ROBOT_BEHAVIOR_ALIASES.items():
        key = normalize_text(str(alias))
        if key and key in text_norm:
            return str(behavior_id)
    return None


def _kw_any(t: str, phrases: tuple[str, ...]) -> bool:
    return any(p in t for p in phrases)


def _is_explicit_stand_command(text: str) -> bool:
    """
    Lệnh đứng rõ ràng (vd. «đứng», «đứng lên giúp mình») — dùng để không tin pose_state suy ra (hay sai) và vẫn gọi stand_up.
    Giới hạn từ giống _is_explicit_sit_command (8), tránh câu dài vẫn bị coi là không «explicit» rồi skip đứng.
    """
    raw = (text or "").strip()
    if not raw:
        return False
    t = normalize_text(raw)
    if len(t.split()) > 8:
        return False
    return _classify_keyword_action(t, raw, skip_speak_text=True) == "stand"


def _is_explicit_sit_command(text: str) -> bool:
    """Lệnh ngồi ngắn — vẫn gọi sit_down khi pose_state suy ra sai (robot chưa ngồi nhưng bị coi là sitting)."""
    raw = (text or "").strip()
    if not raw:
        return False
    t = normalize_text(raw)
    if len(t.split()) > 8:
        return False
    return _classify_keyword_action(t, raw, skip_speak_text=True) == "sit_down"


def _dung_stand_vs_stop(t: str, raw: str) -> str | None:
    """
    Sau normalize, 'đứng' và 'dừng' đều thành 'dung' — phải nhìn chuỗi gốc.
    Một mình 'dung' không dấu: ưu tiên stand (đứng dậy) cho robot.
    """
    if t.strip() != "dung":
        return None
    r = (raw or "").casefold()
    if "dừng" in r:
        return "stop"
    if "đứng" in r:
        return "stand"
    return "stand"


# Cum sau "noi ..." neu la lenh co the (khong phai doc cau tho) -> uu tien intent dong tac, khong speak_text.
_NOI_PHRASE_MOTION_ACTIONS = frozenset(
    {
        "dance",
        "mixi_show",
        "quy_khoi_show",
        "turn_left",
        "turn_right",
        "walk_forward",
        "stop",
        "sit_down",
        "sit_then_stand",
        "stand",
    }
)


def _classify_keyword_action(
    t: str, raw: str = "", *, skip_speak_text: bool = False
) -> str | None:
    """
    Phân loại hành động chỉ bằng chuỗi đã normalize_text (không dấu, đ->d).
    Thứ tự if quan trọng: cụm dài / từ chối trước.
    """
    # --- từ chối / ngoại lệ (không chặn câu lịch sự có lệnh robot: «xin lỗi, bạn ngồi giúp») ---
    if _kw_any(
        t,
        (
            "xin loi",
            "sorry",
            "khong can",
            "thoi khong",
            "dung noi",
        ),
    ):
        _motion = any(
            x in t
            for x in (
                "ngoi",
                "sit down",
                "squat",
                "dung len",
                "dung day",
                "stand up",
                "get up",
                "nhay",
                "quay trai",
                "quay phai",
                "di toi",
                "dung lai",
                "stop",
            )
        ) or ("mua" in t.split() or (len(t.split()) == 1 and t.strip() in ("sit", "squat", "stand")))
        if not _motion:
            return None
    # "noi ..." / say ... — neu cum sau "noi" la lenh co the (ngoi, nhay, ...) thi KHONG speak_text
    if not skip_speak_text:
        raw_in = (raw or "").strip() or t
        sp_after = _extract_speak_phrase_after_noi(raw_in)
        if sp_after:
            tp = normalize_text(sp_after)
            inner = _classify_keyword_action(tp, sp_after, skip_speak_text=True)
            if inner not in _NOI_PHRASE_MOTION_ACTIONS:
                return "speak_text"
    if _kw_any(t, ("khong nhay", "dung nhay", "thoi nhay", "ngung nhay", "no dance", "dont dance")):
        pass
    else:
        # múa võ / kung fu — cùng action dance; behavior = ROBOT_MARTIAL_BEHAVIOR (resolve_behavior_from_message)
        if _martial_intent_keywords_norm(t):
            return "dance"
        # dance / múa (ưu tiên cụm trước từ đơn)
        if _kw_any(
            t,
            (
                "khieu vu",
                "bieu dien",
                "nhay nhot",
                "nhay theo",
                "nhay di",
                "nhay mot bai",
                "nhay mot dieu",
                "flash mob",
                "disco",
                "boogie",
                "shuffle",
                "twist",
                "macarena",
                "tango",
                "salsa",
                "hip hop",
                "vun nhay",
                "len san",
                "len san nhay",
                "nhay cho",
                "lac minh",
                "lac lung",
                "shake body",
                "bounce",
                "groove",
                "party dance",
                "rock and roll",
                "swing dance",
                "na na na na",
                "na na na",
                "anh do mixi",
                "do mixi",
                "nhay bai",
            ),
        ) or (
            any(w in t.split() for w in ("nhay", "mua", "dance"))
            and not _kw_any(t, ("khong nhay", "dung nhay", "thoi nhay", "ngung nhay"))
        ):
            return "dance"

    # --- ngồi -> đứng (câu có cả hai yêu cầu) ---
    # Trường hợp user chat 1 câu: "ngồi và đứng"/"ngồi rồi đứng lên"...
    # Backend hiện chỉ hỗ trợ 1 action/1 tin → ta map sang action đặc biệt sit_then_stand.
    raw_l = (raw or "").casefold()
    wants_sit = _kw_any(
        t,
        (
            "ngoi",
            "sit down",
            "squat",
            "cui",
            "ha lung",
            "cui xuong",
            "ha minh",
            "nam xuong",
            "kneel down",
        ),
    ) or ("ngoi xuong" in t)
    wants_stand = (
        ("đứng" in raw_l)
        or ("đứng lên" in raw_l)
        or ("đứng dậy" in raw_l)
        or ("đứng dậy" in raw_l)
        or ("stand up" in raw_l)
        or ("get up" in raw_l)
        or ("on your feet" in raw_l)
    )
    # Nếu user đang muốn "dừng" (từ ghép với "đứng" có thể gây mơ hồ), ưu tiên stop.
    if wants_sit and wants_stand and ("dừng" not in raw_l) and not _kw_any(t, ("stop", "dung lai", "ngung")):
        return "sit_then_stand"

    # --- đứng (trước 'dung' stop) ---
    if _kw_any(
        t,
        (
            "dung len",
            "dung day",
            "dung day len",
            "thang nguoi",
            "thang than",
            "day len",
            "ngoi day",
            "dung thang",
            "dung day di",
            "stand up",
            "get up",
            "rise",
            "wake up",
            "dung han len",
            "dung thang nguoi",
            "dung day nguoi",
            "on your feet",
            "dung len sau khi ngoi",
            "dung day sau khi ngoi",
            "sau khi ngoi dung len",
            "sau khi ngoi dung day",
            "sau khi ngoi hay dung len",
            "tu the ngoi dung len",
            "thang lai",
            "vuon minh",
            "thang nguoi len",
            "dung thang day",
            "dunglen",  # gõ dính: đứnglên
        ),
    ) or ("stand" in t and "understand" not in t and "withstand" not in t):
        return "stand"

    # --- ngồi ---
    if _kw_any(
        t,
        (
            "ngoi xuong",
            "sit down",
            "squat",
            "het xuong",
            "ha mom",
            "ha lung",
            "lot xuong",
            "cui nguoi",
            "cui xuong",
            "nam xuong",
            "nam ra",
            "phuc xuong",
            "take a seat",
            "have a seat",
            "sitting",
            "ngoi di",
            "ngoi nghi",
            "ha minh",
            "kneel down",
            "lam ngoi",
            "hay ngoi",
            "hay ngoi xuong",
            "lam on ngoi",
            "lam on ngoi xuong",
            "robot ngoi",
            "mini ngoi",
            "alpha mini ngoi",
            "ban ngoi",
            "ban ngoi xuong",
            "thuc hien ngoi",
            "dong tac ngoi",
            "ngoi nao",
            "ngoi nao di",
            "ngoi xuong di",
            "ngoi giup",
            "ngoi giup minh",
            "ngoi xuong giup",
        ),
    ) or (" hay ngoi" in f" {t} "):
        return "sit_down"
    toks = t.split()
    if ("ngoi" in toks or t.strip() in ("sit", "squat")) and "ngoi day" not in t:
        return "sit_down"

    # --- quay trái / phải (trước walk có 'buoc') ---
    if _kw_any(
        t,
        (
            "quay phai",
            "xoay phai",
            "re phai",
            "vong phai",
            "sang phai",
            "turn right",
            "right turn",
            "ben phai",
            "ve phia phai",
        ),
    ) or (("quay" in t or "xoay" in t or "re" in t) and "phai" in t):
        return "turn_right"
    if _kw_any(
        t,
        (
            "quay trai",
            "xoay trai",
            "re trai",
            "vong trai",
            "sang trai",
            "turn left",
            "left turn",
            "ben trai",
            "ve phia trai",
        ),
    ) or (("quay" in t or "xoay" in t or "re" in t) and "trai" in t):
        return "turn_left"

    # --- đi tới ---
    if _kw_any(
        t,
        (
            "di toi",
            "di len",
            "tien len",
            "tien toi",
            "buoc len",
            "buoc toi",
            "di thang",
            "di ve phia truoc",
            "len phia truoc",
            "len truoc",
            "walk forward",
            "move forward",
            "come forward",
            "step forward",
            "march",
            "lai day",
            "lai gan",
            "den day",
            "toi day",
            "buoc toi truoc",
            "di chuyen len",
            "move ahead",
            "go ahead",
            "tiep can",
        ),
    ) or "advance" in toks:
        return "walk_forward"

    # --- dừng (sau khi xử lý đứng/dừng một âm tiết) ---
    _ds = _dung_stand_vs_stop(t, raw)
    if _ds is not None:
        return _ds
    if _kw_any(
        t,
        (
            "dung lai",
            "dung yen",
            "stop",
            "ngung",
            "tam dung",
            "thoi di",
            "dung han",
            "halt",
            "pause",
            "dung hoat dong",
            "stop lai",
            "thoi nhac",
            "tat nhac",
            "im lang",
            "yen lang",
            "im dien",
            "dung dong",
            "freeze",
            "hold it",
            "thoi dien",
        ),
    ):
        return "stop"
    if "dung" in t and any(x in t for x in ("nhay", "mua", "nhac")):
        return "stop"

    # --- chào / tạm biệt (wave nhẹ = greet) ---
    if _kw_any(
        t,
        (
            "xin chao",
            "hello",
            "hi ",
            "chao ban",
            "chao nha",
            "chao em",
            "chao anh",
            "chao chi",
            "chao co",
            "chao thay",
            "chao ong",
            "chao ba",
            "chao chu",
            "chao buoi sang",
            "chao buoi chieu",
            "chao buoi toi",
            "good morning",
            "good evening",
            "good afternoon",
            "good night",
            "hey ",
            "alo ",
            "a lo",
            "tam biet",
            "bye bye",
            "goodbye",
            "see you",
            "chao hen gap lai",
            "huy ho",
            "vay tay chao",
            "vay tay",
            "cui chao",
            "chuc mung",
            "nice to meet",
        ),
    ):
        return "greet"
    if any(w in toks for w in ("chao", "hello", "hi", "hey", "alo", "bye", "wave")):
        return "greet"

    return None


def _wants_quy_khoi_choreography(t_norm: str) -> bool:
    """Chat: Quỷ Khói / Tày Note → timeline anime + Bollywood."""
    if "quy khoi" in t_norm:
        return True
    if "tay note" in t_norm:
        return True
    return False


def _wants_mixi_choreography(t_norm: str) -> bool:
    """Chat: nà ná na na / anh độ mixi → full bài (nhạc + vũ đạo v3)."""
    if "na na na na" in t_norm or "na na na" in t_norm:
        return True
    if "anh do mixi" in t_norm:
        return True
    if t_norm.strip() == "do mixi":
        return True
    return False


def _wants_o_i_i_choreography(t_norm: str) -> bool:
    """Bài Ộ I I / Alo Vũ (dances/o_i_i_dance.py). Kèm «nà ná na na» → nhạc nền na na (O_I_I_NA_NA_BACKING)."""
    return _kw_any(
        t_norm,
        (
            "o i i",
            "oii",
            "oi i",
            "alo vu",
            "hoi i",
        ),
    )


def _o_i_i_with_na_na_backing(t_norm: str) -> bool:
    """Cùng câu có cả cụm na na và o i i → bật nhạc nền nà ná na na cho show Ộ I I."""
    if not _wants_o_i_i_choreography(t_norm):
        return False
    return ("na na na na" in t_norm) or ("na na na" in t_norm)


def keyword_intent(text: str) -> dict | None:
    """Heuristic từ khóa — cover tiếng Việt/Anh giao tiếp thường."""
    t = normalize_text(text)
    if _wants_quy_khoi_choreography(t):
        return {
            "action": "quy_khoi_show",
            "behavior": None,
            "audio_url": None,
        }
    if _wants_o_i_i_choreography(t):
        return {
            "action": "o_i_i_show",
            "behavior": None,
            "audio_url": None,
            "o_i_i_na_na_backing": _o_i_i_with_na_na_backing(t),
        }
    if _wants_mixi_choreography(t):
        return {
            "action": "mixi_show",
            "behavior": None,
            "audio_url": None,
        }
    u = _extract_url_from_text(text)
    if u:
        u_low = u.lower()
        yt = "youtube.com" in u_low or "youtu.be" in u_low
        media_kw = _kw_any(
            t,
            (
                "nhac",
                "phat",
                "play",
                "mo",
                "bat",
                "link",
                "nghe",
                "hat",
                "stream",
                "url",
                "youtube",
                "mp3",
                "bai hat",
            ),
        )
        dance_kw = _kw_any(
            t,
            (
                "nhay",
                "mua",
                "khieu vu",
                "bieu dien",
                "nhay theo",
                "nhay bai",
            ),
        ) or any(w in t.split() for w in ("nhay", "mua"))
        if media_kw or dance_kw or yt:
            also_dance = bool(dance_kw)
            beh = resolve_behavior_from_message(t) if also_dance else None
            return {
                "action": "play_audio",
                "behavior": beh,
                "audio_url": u,
                "also_dance": also_dance,
            }

    act = _classify_keyword_action(t, text)
    if not act:
        return None
    if act == "speak_text":
        phrase = _extract_speak_phrase_after_noi(text)
        if not phrase:
            return None
        return {
            "action": "speak_text",
            "behavior": None,
            "audio_url": None,
            "speak_text": phrase,
        }
    if act == "dance":
        return {
            "action": "dance",
            "behavior": resolve_behavior_from_message(t),
            "audio_url": None,
        }
    return {"action": act, "behavior": None, "audio_url": None}


# ── Gemini setup ─────────────────────────────────────────
if not config.GEMINI_API_KEY:
    raise RuntimeError(
        "Missing GEMINI_API_KEY. Please set it in .env file."
    )

client = genai.Client(api_key=config.GEMINI_API_KEY)
chat_session = client.chats.create(
    model=config.GEMINI_MODEL,
    config=types.GenerateContentConfig(
        system_instruction=config.SYSTEM_PROMPT
    )
)

_INTENT_ACTIONS = frozenset({
    "none",
    "dance",
    "mixi_show",
    "quy_khoi_show",
    "o_i_i_show",
    "turn_left",
    "turn_right",
    "walk_forward",
    "stop",
    "greet",
    "speak_text",
    "play_audio",
    "sit_down",
    "sit_then_stand",
    "stand",
})


def _safe_http_url(u: str | None) -> str | None:
    if not u or not isinstance(u, str):
        return None
    u = u.strip()
    return u if u.startswith(("http://", "https://")) else None


def _extract_url_from_text(text: str) -> str | None:
    m = re.search(r"https?://[^\s\"'<>]+", text)
    if not m:
        return None
    return m.group(0).rstrip(").,]\"'")


def _parse_intent_json(raw: str) -> dict | None:
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```\s*$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    action = str(data.get("action", "none")).strip().lower()
    if action not in _INTENT_ACTIONS:
        action = "none"
    behavior = data.get("behavior")
    if behavior is not None:
        behavior = str(behavior).strip() or None
    audio_url = _safe_http_url(data.get("audio_url"))
    speak_text = data.get("speak_text")
    if speak_text is not None:
        speak_text = str(speak_text).strip() or None
    return {
        "action": action,
        "behavior": behavior,
        "audio_url": audio_url,
        "speak_text": speak_text,
    }


def llm_robot_intent(user_text: str) -> dict | None:
    """Gemini phân loại ý định → JSON cố định."""
    if not user_text.strip():
        return None
    instruction = (
        "Ban la bo loc lenh dieu khien robot. Chi tra ve JSON hop le, khong markdown, khong giai thich.\n"
        'Bat buoc co 3 key: "action", "behavior", "audio_url".\n'
        '"action" chi mot trong: none, dance, mixi_show, quy_khoi_show, o_i_i_show, turn_left, turn_right, walk_forward, stop, greet, speak_text, play_audio, sit_down, sit_then_stand, stand.\n'
        '"behavior": string hoac null (ma behavior robot, vi du dance_0004).\n'
        '"audio_url": string URL http(s) hoac null.\n'
        '"speak_text": string cum robot can noi (bat buoc khi action la speak_text), hoac null.\n\n'
        "Quy tac:\n"
        "- dance: nguoi muon nhay, mua, khieu vu, bieu dien, quay nguoi theo dieu nhac; mua vo / kung fu / vo thuat cung la dance (behavior tuy firmware).\n"
        "- quy_khoi_show: bai Quy Khoi / Tay Note, Do Mixi / choreography dac biet, anime opening + Bollywood.\n"
        "- o_i_i_show: bai O I I / Alo Vu (dances/o_i_i_dance); neu co ca na na na va o i i thi nhac nen na na (nhu O_I_I_NA_NA_BACKING).\n"
        "- turn_left / turn_right: quay trai/phai, re trai/phai, xoay trai/phai.\n"
        "- walk_forward: di toi, buoc len, tien len, di thang.\n"
        "- stop: dung lai, ngung, tat nhac nhay.\n"
        "- greet: chao hoi (vay tay / chao ngan), khong phai doc mot cau tuy chon.\n"
        "- speak_text: nguoi yeu cau robot NOI ra mot cum cu the (vi du 'noi cam on ban', 'hay noi xin chao', 'say hello everyone'). Dat speak_text = cum do (khong gom tu 'noi'/'say').\n"
        "- play_audio: bat nhac / phat nhac va co URL ro rang trong cau.\n"
        "- sit_down: ngoi, ngoi xuong, cui, squat.\n"
        "- sit_then_stand: ngoi rồi dung day/dung len.\n"
        "- stand: dung day, dung len, thang nguoi, day len.\n"
        "- none: hoi dap tinh cam, khong yeu cau co the.\n\n"
        "Cau nguoi dung (nguyen van):\n"
    )
    payload = instruction + json.dumps(user_text, ensure_ascii=False)
    try:
        resp = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=payload,
            config=types.GenerateContentConfig(temperature=0.05),
        )
        return _parse_intent_json(resp.text or "")
    except Exception as e:
        log.warning(f"llm_robot_intent error: {e}")
        return None


async def plan_robot_intent(text: str) -> dict | None:
    """Ưu tiên keyword (on-device), chỉ gọi LLM khi bật ROBOT_SMART_INTENT và không khớp."""
    kw = keyword_intent(text)
    if kw is not None:
        return kw
    # Fallback: nếu keyword không khớp (phiên bản cũ / biên) nhưng rõ «múa võ» — vẫn trả plan dance.
    t_norm = normalize_text(text)
    if _martial_intent_keywords_norm(t_norm):
        return {
            "action": "dance",
            "behavior": resolve_behavior_from_message(t_norm),
            "audio_url": None,
        }
    if not config.ROBOT_SMART_INTENT:
        return None
    try:
        plan = await asyncio.wait_for(
            asyncio.to_thread(llm_robot_intent, text),
            timeout=10.0,
        )
        if plan and plan.get("action") not in (None, "none", ""):
            if plan.get("action") == "play_audio":
                if not plan.get("audio_url"):
                    plan["audio_url"] = _extract_url_from_text(text)
                if not plan.get("audio_url"):
                    return None
            if plan.get("action") == "speak_text":
                st = (plan.get("speak_text") or "").strip()
                if not st:
                    plan["speak_text"] = _extract_speak_phrase_after_noi(text)
                if not (plan.get("speak_text") or "").strip():
                    return None
            return plan
    except asyncio.TimeoutError:
        log.warning("plan_robot_intent: LLM timeout")
    except Exception as e:
        log.warning(f"plan_robot_intent: {e}")
    return None


def _stop_all_choreography_loops() -> None:
    """Tắt các vòng dance_loop (mixi / quy_khoi / belly) — an toàn gọi nhiều lần."""
    try:
        from dances.an_do_mixi_dance import stop_mixi_dance
        from dances.belly_dance import stop_belly_dance
        from dances.dual_song_dance import stop_dual_song_dance
        from dances.o_i_i_dance import stop_o_i_i_dance
        from dances.quy_khoi_tay_note_show import stop_quy_khoi_dance

        stop_mixi_dance()
        stop_quy_khoi_dance()
        stop_belly_dance()
        stop_o_i_i_dance()
        stop_dual_song_dance()
    except Exception:
        pass


async def execute_intent_plan(plan: dict, original_text: str):
    await ensure_robot_for_commands()
    if not plan:
        return
    if not robot_sdk_session_ok():
        act = (plan or {}).get("action")
        if act and act not in ("none", None):
            log.warning(
                "🤖 execute_intent_plan: bỏ qua action=%s — robot chưa kết nối SDK. "
                "Cùng Wi‑Fi với robot, POST /robot/reconnect hoặc restart server; kiểm tra GET /status (robot_online).",
                act,
            )
        return
    async with _robot_action_lock:
        _stop_all_choreography_loops()
        action = plan.get("action")
        if action in (None, "none"):
            return
        # Tránh gọi stop quá sớm khi đang chuyển từ "ngồi" -> "đứng"
        # (trong thực tế có thể làm robot tụt lưng trước khi kịp đứng).
        pose_now = getattr(robot, "pose_state", None)
        # Khong goi StopAllAction truoc TTS / nhay: tren nhieu firmware stop() tat loa truoc StartBehavior -> het nhac nen vu dao.
        skip_stop = (action == "stand" and pose_now == "sitting") or (
            action == "sit_then_stand" and pose_now == "sitting"
        ) or action in ("speak_text", "greet", "dance")
        if not skip_stop:
            try:
                await robot.stop()
            except Exception:
                pass
        tnorm = normalize_text(original_text)
        behavior = plan.get("behavior") or resolve_behavior_from_message(tnorm)
        audio_url = plan.get("audio_url") or _extract_url_from_text(original_text)
        try:
            if action == "mixi_show":
                # Choreography có thể đổi tư thế → bỏ qua pose inference.
                robot.pose_state = None
                from dances.an_do_mixi_dance import run_mixi_show

                log.info("🤖 intent: mixi_show (An Do Mixi v4 — nhac + vu dao)")
                await run_mixi_show()
            elif action == "o_i_i_show":
                robot.pose_state = None
                from dances.o_i_i_dance import run_o_i_i_show

                na = bool(plan.get("o_i_i_na_na_backing"))
                prev_na = os.environ.get("O_I_I_NA_NA_BACKING")
                try:
                    if na:
                        os.environ["O_I_I_NA_NA_BACKING"] = "1"
                        log.info(
                            "🤖 o_i_i_show: nhạc nền Nà ná na na (O_I_I_NA_NA_BACKING=1, xem AN_DO_MIXI_MP3_URL / .env)"
                        )
                    log.info("🤖 intent: o_i_i_show (Ộ I I — Alo Vũ, dances/o_i_i_dance)")
                    await run_o_i_i_show()
                finally:
                    if na:
                        if prev_na is None:
                            os.environ.pop("O_I_I_NA_NA_BACKING", None)
                        else:
                            os.environ["O_I_I_NA_NA_BACKING"] = prev_na
            elif action == "quy_khoi_show":
                robot.pose_state = None
                from dances.quy_khoi_tay_note_show import run_quy_khoi_show

                log.info("🤖 intent: quy_khoi_show (Quy Khoi & Tay Note — nhac + vu dao)")
                await run_quy_khoi_show()
            elif action == "dance":
                robot.pose_state = None
                if ("na na na na" in tnorm or "na na na" in tnorm) and not behavior:
                    log.warning(
                        "Tu khoa 'na na na na' nhung chua gan behavior rieng — dat "
                        "ROBOT_DANCE_NA_NA_BEHAVIOR=id trong .env hoac JSON ROBOT_BEHAVIOR_ALIASES "
                        '(vd. {"na na na na":"dance_0005"}). Hien dung mac dinh %s. '
                        "Nhac nghe duoc la tu firmware cua vu dao do, khong phai URL ngoai.",
                        config.ROBOT_DEFAULT_BEHAVIOR,
                    )
                await robot.dance(behavior)
                log.info(f"🤖 intent: dance behavior={behavior!r}")
            elif action == "turn_left":
                await robot.turn_left()
                log.info("🤖 intent: turn_left")
            elif action == "turn_right":
                await robot.turn_right()
                log.info("🤖 intent: turn_right")
            elif action == "walk_forward":
                await robot.walk_forward()
                log.info("🤖 intent: walk_forward")
            elif action == "stop":
                await robot.stop()
                log.info("🤖 intent: stop")
            elif action == "speak_text":
                st = (plan.get("speak_text") or "").strip() or _extract_speak_phrase_after_noi(
                    original_text
                )
                if not st:
                    log.warning("speak_text: empty phrase")
                else:
                    st = st[:_MAX_SPEAK_PHRASE_LEN]
                    ok_say = await robot.say(st)
                    if ok_say:
                        log.info("🤖 intent: speak_text ok=%s text=%r", ok_say, st[:80])
                    else:
                        raise RuntimeError(
                            "speak_text: robot.say() that bai — xem log TTS phia tren; can ROBOT_AUDIO_PUBLIC_URL + FPT (hoac dat ROBOT_TTS_MODE=prefer_http)"
                        )
            elif action == "greet":
                # Nếu user yêu cầu "hãy nói xin chào đi" thì nói đúng câu đó,
                # tránh dùng câu chào mặc định.
                custom = _greet_speech_from_text(original_text)
                if custom:
                    ok_say = await robot.say(custom)
                    if not ok_say:
                        raise RuntimeError("greet: robot.say(custom) that bai")
                else:
                    ok_greet = await robot.greet()
                    if not ok_greet:
                        raise RuntimeError("greet: robot.greet() that bai")
                log.info("🤖 intent: greet")
            elif action == "play_audio":
                url = _safe_http_url(audio_url)
                also_dance = bool(plan.get("also_dance"))
                if url:
                    if "youtube.com" in url.lower() or "youtu.be" in url.lower():
                        log.warning(
                            "play_audio: URL la trang YouTube — SDK thuong can link stream mp3 "
                            "truc tiep; neu khong phat duoc hay dung URL mp3 hoac ung dung tren dien thoai."
                        )
                    await robot.play_online_music(url)
                    log.info("🤖 intent: play_audio")
                elif not also_dance:
                    log.warning("play_audio missing valid url")
                if also_dance:
                    robot.pose_state = None
                    await robot.dance(behavior)
                    log.info(f"🤖 intent: dance (kem nhac) behavior={behavior!r}")
            elif action == "sit_then_stand":
                # Nếu user gõ 1 câu có cả "ngồi" và "đứng",
                # ta thực thi tuần tự: (đảm bảo đang ngồi) -> đứng.
                if getattr(robot, "pose_state", None) != "sitting":
                    await robot.sit_down()
                    log.info("🤖 intent: sit_then_stand (do sit_down)")
                else:
                    log.info("🤖 intent: sit_then_stand skipped sit_down (already sitting)")

                if getattr(robot, "pose_state", None) != "standing":
                    await robot.stand_up()
                    log.info("🤖 intent: sit_then_stand (do stand_up)")
                else:
                    log.info("🤖 intent: sit_then_stand skipped stand_up (already standing)")
            elif action == "sit_down":
                explicit_sit = _is_explicit_sit_command(original_text)
                pose_sit = getattr(robot, "pose_state", None) == "sitting"
                if pose_sit and not explicit_sit:
                    log.info("🤖 intent: sit_down skipped (already sitting)")
                else:
                    if pose_sit and explicit_sit:
                        log.info(
                            "🤖 intent: sit_down — lenh ro rang, bo qua pose sitting (pose suy ra co the sai)"
                        )
                        robot.pose_state = None
                    await robot.sit_down()
                    log.info("🤖 intent: sit_down")
            elif action == "stand":
                explicit = _is_explicit_stand_command(original_text)
                try:
                    extra = max(0.0, float(config.ROBOT_STAND_AFTER_INTENT_STOP_SEC))
                except (TypeError, ValueError):
                    extra = 0.45
                if extra > 0:
                    await asyncio.sleep(extra)
                pose = getattr(robot, "pose_state", None)
                ignore_pose = bool(
                    explicit and getattr(config, "ROBOT_STAND_IGNORE_POSE_WHEN_EXPLICIT", True)
                )
                # Không skip khi pose_state=standing: suy luật pose hay sai sau nhảy/ngồi — bỏ sót lệnh «đứng».
                if pose == "standing" and not ignore_pose:
                    log.info(
                        "🤖 intent: stand — pose=standing nhưng vẫn gọi stand_up (tránh bỏ sót khi pose sai)"
                    )
                if ignore_pose and pose == "standing":
                    log.info(
                        "🤖 intent: stand — explicit command, bỏ qua pose standing (pose suy ra có thể sai)"
                    )
                    robot.pose_state = None

                async def _do_stand():
                    await robot.stand_up()

                try:
                    await _do_stand()
                except RuntimeError as e:
                    if not getattr(config, "ROBOT_STAND_RETRY_ON_FAIL", True):
                        raise
                    log.warning("stand_up lần 1 thất bại: %s — thử lại sau stop", e)
                    try:
                        await robot.stop()
                    except Exception:
                        pass
                    await asyncio.sleep(1.0)
                    robot.pose_state = None
                    await robot.stand_up()
                log.info("🤖 intent: stand")
            else:
                log.warning(f"unknown intent action: {action}")
        except asyncio.CancelledError:
            log.info("execute_intent_plan: cancelled (lenh moi)")
            raise
        except Exception as e:
            log.warning(f"execute_intent_plan: {e}")
            raise


# ── Robot setup ───────────────────────────────────────────
robot = None
_LAST_ROBOT_CONNECT_ERROR: str | None = None
_robot_intent_task: asyncio.Task | None = None
_robot_action_lock = asyncio.Lock()
_robot_tts_lock = asyncio.Lock()
_last_robot_say_text: str = ""
_last_robot_say_ts: float = 0.0
# filename -> monotonic timestamp lần gần nhất endpoint /robot/tts_media/{filename} được tải.
_TTS_MEDIA_LAST_HIT: dict[str, float] = {}
# JPEG gần nhất từ /robot/camera/frame (giảm tần suất take_picture khi nhiều client).
_ROBOT_FRAME_CACHE: bytes | None = None
_ROBOT_FRAME_TS: float = 0.0
# Sau mỗi lần connect_robot OK: cho phép một lần enter_program+khi code=-2 khi chụp.
_TAKE_PICTURE_ENTER_PROGRAM_RETRIED_THIS_SESSION = False


async def _cancel_pending_robot_intent_task() -> None:
    """Hủy intent đang chạy (vd. mixi_show) trước khi chạy lệnh chat/trigger mới."""
    global _robot_intent_task
    _stop_all_choreography_loops()
    if _robot_intent_task and not _robot_intent_task.done():
        _robot_intent_task.cancel()
        try:
            await _robot_intent_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.debug("pending robot intent cleanup: %s", e)
    _robot_intent_task = None


def _set_robot_type_from_config() -> None:
    """Ánh xạ ROBOT_TYPE (.env) → mini_sdk.RobotType (mDNS + handshake đúng dòng máy)."""
    from mini import mini_sdk

    t = (config.ROBOT_TYPE or "mini").strip().lower()
    if t in ("mini", "min"):
        mini_sdk.set_robot_type(mini_sdk.RobotType.MINI)
    elif t == "edu":
        mini_sdk.set_robot_type(mini_sdk.RobotType.EDU)
    elif t in ("dedu", "cn", "china"):
        mini_sdk.set_robot_type(mini_sdk.RobotType.DEDU)
    elif t in ("kor", "kr"):
        mini_sdk.set_robot_type(mini_sdk.RobotType.KOR)
    else:
        log.warning("ROBOT_TYPE=%r không hợp lệ (mini|edu|dedu|kor) — dùng MINI", config.ROBOT_TYPE)
        mini_sdk.set_robot_type(mini_sdk.RobotType.MINI)


class AlphaMiniClient:
    def __init__(self, ip: str):
        self.ip = ip
        self.connected = False
        # Best-effort pose tracking: suy ra tư thế từ lệnh gần nhất.
        # SDK hiện không expose trực tiếp “pose hiện tại” (standing/sitting).
        self.pose_state: str | None = None
        # Sau StartBehavior(nhảy) thành công, lần nhảy tiếp theo cần StopAllAction trước — nhiều firmware bỏ qua StartBehavior nếu behavior cũ chưa dừng.
        self._need_stop_before_next_dance: bool = False

    async def connect(self):
        from mini import mini_sdk
        from mini.dns.dns_browser import WiFiDevice

        _set_robot_type_from_config()
        log.info("🤖 Robot SDK: ROBOT_TYPE=%s", config.ROBOT_TYPE)
        device = WiFiDevice(name="AlphaMini", address=self.ip)
        self.connected = await mini_sdk.connect(device)
        if not self.connected:
            raise RuntimeError(f"Cannot connect to robot at {self.ip}")
        self.pose_state = None
        self._need_stop_before_next_dance = False

        try:
            prog_ok = await mini_sdk.enter_program()
        except asyncio.CancelledError:
            # Một số firmware/SDK có thể huỷ await nội bộ khi chuyển mode; không để crash request /chat.
            prog_ok = False
            log.warning("enter_program() bị huỷ (CancelledError) — bỏ qua và tiếp tục phiên robot")
        except Exception as e:
            prog_ok = False
            log.warning("enter_program() lỗi: %s", e)
        if not prog_ok:
            log.warning(
                "enter_program() không báo Success — robot có thể chưa sẵn sàng nhận PlayAction/MoveRobot; "
                "đợi vài giây hoặc thử ROBOT_TYPE=edu nếu là bản quốc tế."
            )

    async def disconnect(self):
        if not self.connected:
            return
        from mini import mini_sdk
        await mini_sdk.release()
        self.connected = False
        self.pose_state = None
        self._need_stop_before_next_dance = False

    @staticmethod
    def _is_api_success(result) -> bool:
        # Some SDK calls return bool, others return (resultType, response).
        if isinstance(result, bool):
            return result
        if isinstance(result, tuple) and len(result) == 2:
            result_type, response = result
            return getattr(result_type, "name", "") == "Success" and bool(getattr(response, "isSuccess", False))
        return False

    async def _say_via_http_audio(self, text: str) -> bool:
        """TTS bên ngoài (MP3) + play_online_audio — robot phải tải được URL (ROBOT_AUDIO_PUBLIC_URL = IP máy PC)."""
        base = config.robot_audio_fetch_base_url()
        if not base:
            log.warning("ROBOT_AUDIO_PUBLIC_URL trống — bỏ qua TTS HTTP")
            return False
        try:
            path = await synthesize_tts_mp3_to_cache(text)
        except Exception as e:
            log.warning(f"synthesize_tts_mp3_to_cache failed: {e}")
            return False
        filename = path.name
        url = f"{base}/robot/tts_media/{filename}"
        t0 = time.monotonic()
        raw_env = (config.ROBOT_AUDIO_PUBLIC_URL or "").strip().rstrip("/")
        if raw_env and raw_env.lower().startswith("http://") and base.lower().startswith("https://"):
            log.info("🔊 TTS URL dung https (dong bo voi server SSL): %s", url[:120])
        try:
            from mini import mini_sdk

            if getattr(config, "ROBOT_SET_VOLUME_BEFORE_TTS", False):
                try:
                    vol = float(getattr(config, "ROBOT_TTS_VOLUME", 0.95) or 0.95)
                    await mini_sdk.change_volume(max(0.0, min(1.0, vol)))
                    log.info(f"🔊 set volume before HTTP TTS: {vol}")
                except Exception as ve:
                    log.warning(f"change_volume failed: {ve}")
            try:
                await mini_sdk.stop_tts()
            except Exception:
                pass
            try:
                await mini_sdk.stop_audio()
            except Exception:
                pass
            ok = await mini_sdk.play_online_audio(url)
            log.info(f"🔊 play_online_audio(TTS) ok={ok} url={url[:96]}...")
            if ok:
                # Một số firmware trả ok=True nhưng không hề tải URL (và robot im lặng).
                wait_sec = float(getattr(config, "ROBOT_TTS_FETCH_WAIT_SEC", 2.5) or 0.0)
                if wait_sec > 0:
                    deadline = time.monotonic() + wait_sec
                    fetched = False
                    while time.monotonic() < deadline:
                        hit = _TTS_MEDIA_LAST_HIT.get(filename, 0.0)
                        if hit >= t0:
                            fetched = True
                            break
                        await asyncio.sleep(0.12)
                    if not fetched:
                        log.warning(
                            "🔊 TTS HTTP: robot chưa GET /robot/tts_media/%s trong %.1fs (ok=True nhưng có thể im lặng)",
                            filename,
                            wait_sec,
                        )
                        # Có firmware trả trạng thái/telemetry không ổn định: đã phát nhưng miss dấu hit.
                        # Không hạ kết quả thành lỗi nếu play_online_audio đã ok=True.
                        log.info("🔊 TTS HTTP: giữ ok=True vì play_online_audio đã thành công")
                asyncio.create_task(_unlink_later(path, 600.0))
            else:
                path.unlink(missing_ok=True)
            return bool(ok)
        except Exception as e:
            log.warning(f"_say_via_http_audio failed: {e}")
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            return False

    async def _say_via_sdk(self, text: str) -> bool:
        # Many firmwares do not support TTS over this SDK (resultCode 404).
        try:
            from mini.apis.api_sound import StartPlayTTS
            if getattr(config, "ROBOT_SET_VOLUME_BEFORE_TTS", False):
                try:
                    from mini import mini_sdk

                    vol = float(getattr(config, "ROBOT_TTS_VOLUME", 0.95) or 0.95)
                    await mini_sdk.change_volume(max(0.0, min(1.0, vol)))
                    log.info(f"🔊 set volume before TTS: {vol}")
                except Exception as ve:
                    log.warning(f"change_volume failed: {ve}")
            try:
                from mini import mini_sdk
                await mini_sdk.stop_tts()
            except Exception:
                pass
            try:
                from mini import mini_sdk
                await mini_sdk.stop_audio()
            except Exception:
                pass

            result = await StartPlayTTS(True, text).execute()
            ok = self._is_api_success(result)
            log.info(f"🔊 StartPlayTTS ok={ok}")
            if not ok:
                raise RuntimeError(f"play_tts failed or unsupported: {result!r}")
            return True
        except Exception as e:
            log.warning(f"robot._say_via_sdk failed: {e}")
            return False

    async def say(self, text: str):
        mode = (config.ROBOT_TTS_MODE or "sdk").strip().lower()
        if mode not in ("sdk", "http_only", "prefer_http"):
            mode = "sdk"

        if mode == "http_only":
            return await self._say_via_http_audio(text)

        if mode == "prefer_http":
            if await self._say_via_http_audio(text):
                return True
            log.info("🔊 prefer_http: fallback StartPlayTTS")
            return await self._say_via_sdk(text)

        # sdk (mac dinh): nhieu firmware khong co StartPlayTTS / tra loi — fallback HTTP neu da cau hinh URL cong khai.
        if await self._say_via_sdk(text):
            return True
        pub = config.robot_audio_fetch_base_url()
        if pub:
            log.info(
                "🔊 SDK TTS khong thanh cong, thu HTTP TTS (robot tai MP3 tu ROBOT_AUDIO_PUBLIC_URL)"
            )
            return await self._say_via_http_audio(text)
        log.warning(
            "🔊 robot.say: SDK that bai va chua co ROBOT_AUDIO_PUBLIC_URL — chay sync-lan-env.ps1 hoac dat trong .env, hoac ROBOT_TTS_MODE=prefer_http|http_only"
        )
        return False

    async def greet(self):
        return await self.say("Xin chao, minh la Alpha Mini!")

    async def play_behavior_by_name(self, behavior_name: str):
        """Chạy một behavior có sẵn trên robot (tên file/vũ đạo)."""
        try:
            from mini.apis.api_behavior import StartBehavior

            result = await StartBehavior(False, behavior_name).execute()
            return self._is_api_success(result)
        except Exception as e:
            log.warning(f"play_behavior {behavior_name!r} failed: {e}")
            return False

    async def play_online_music(self, url: str):
        """Phát nhạc / stream URL (mp3, wav, amr…) tùy firmware."""
        try:
            from mini import mini_sdk

            return await mini_sdk.play_online_audio(url)
        except Exception as e:
            log.warning(f"play_online_music failed: {e}")
            return False

    async def dance(self, behavior_name: str | None = None):
        name = (behavior_name or config.ROBOT_DEFAULT_BEHAVIOR).strip()
        if self._need_stop_before_next_dance:
            log.info("dance: dừng behavior trước (nhảy lặp / firmware cần reset trước StartBehavior)")
            try:
                await self.stop()
            except Exception as e:
                log.warning("dance: StopAllAction trước nhảy lặp: %s", e)
            try:
                delay = float(getattr(config, "ROBOT_STOP_BEFORE_REPEAT_DANCE_SEC", 0.2) or 0.2)
                await asyncio.sleep(max(0.0, delay))
            except Exception:
                pass
        # Nhac vu dao = am goc trong firmware cua behavior; dam bao volume > 0 (nhieu may mac dinh im).
        if getattr(config, "ROBOT_SET_VOLUME_BEFORE_TTS", True):
            try:
                from mini import mini_sdk

                vol = float(getattr(config, "ROBOT_TTS_VOLUME", 0.95) or 0.95)
                await mini_sdk.change_volume(max(0.0, min(1.0, vol)))
                log.info("🔊 change_volume trước dance: %s", vol)
            except Exception as e:
                log.warning("change_volume trước dance: %s", e)
        if await self.play_behavior_by_name(name):
            self._need_stop_before_next_dance = True
            log.info("dance: StartBehavior OK %r (nhạc do firmware behavior, neu co)", name)
            return

        self._need_stop_before_next_dance = False
        log.warning(
            "dance: không chạy được behavior %r — fallback quay trái/phải (không nhạc). "
            "GET /robot/behaviors → chọn id có âm thanh; đặt ROBOT_DEFAULT_BEHAVIOR hoặc alias trong .env.",
            name,
        )
        await self.turn_right()
        await self.turn_left()

    async def walk_forward(self):
        from mini.apis.api_action import MoveRobot
        from mini import MoveRobotDirection

        result = await MoveRobot(False, MoveRobotDirection.FORWARD, 1).execute()
        if not self._is_api_success(result):
            raise RuntimeError("move FORWARD failed")

    async def stop(self):
        from mini.apis.api_action import StopAllAction

        result = await StopAllAction(False).execute()
        if not self._is_api_success(result):
            raise RuntimeError("stop_action failed")
        self._need_stop_before_next_dance = False

    async def turn_left(self):
        from mini.apis.api_action import MoveRobot
        from mini import MoveRobotDirection

        result = await MoveRobot(False, MoveRobotDirection.LEFTWARD, 1).execute()
        if not self._is_api_success(result):
            raise RuntimeError("move LEFTWARD failed")

    async def turn_right(self):
        from mini.apis.api_action import MoveRobot
        from mini import MoveRobotDirection

        result = await MoveRobot(False, MoveRobotDirection.RIGHTWARD, 1).execute()
        if not self._is_api_success(result):
            raise RuntimeError("move RIGHTWARD failed")

    async def _try_play_inner_actions(self, names: list[str]) -> bool:
        """Inner → PlayAction async → play_custom_action (/sdcard) — tên có thể chỉ khớp một lớp."""
        from mini import mini_sdk
        from mini.apis.api_action import PlayAction

        for name in names:
            if not name:
                continue
            try:
                if await mini_sdk.play_action(name):
                    log.info("robot: play_action OK %r", name)
                    return True
            except Exception as e:
                log.warning("play_action %r: %s", name, e)
            try:
                result = await PlayAction(False, name).execute()
                if self._is_api_success(result):
                    log.info("robot: PlayAction(async) OK %r", name)
                    return True
            except Exception as e:
                log.warning("PlayAction async %r: %s", name, e)
            try:
                if await mini_sdk.play_custom_action(name):
                    log.info("robot: play_custom_action OK %r", name)
                    return True
            except Exception as e:
                log.warning("play_custom_action %r: %s", name, e)
        return False

    async def _try_behavior_names(self, names: list[str]) -> bool:
        """Fallback giống đường nhảy: StartBehavior — một số máy đăng ký ngồi/đứng như behavior chứ không phải inner action."""
        for name in names:
            if not name:
                continue
            if await self.play_behavior_by_name(name):
                log.info("robot: StartBehavior OK %r", name)
                return True
        return False

    async def _try_inner_actions(self, names: list[str]) -> bool:
        """Tương thích tên cũ — chỉ inner action."""
        return await self._try_play_inner_actions(names)

    async def sit_down(self):
        # Dừng motor rồi chờ robot đứng vững — giảm ngã khi vào tư thế ngồi.
        try:
            await self.stop()
        except Exception:
            pass
        try:
            delay = max(0.2, float(config.ROBOT_SIT_STOP_SETTLE_SEC))
        except (TypeError, ValueError):
            delay = 0.65
        await asyncio.sleep(delay)

        seen: set[str] = set()
        ordered: list[str] = []
        # Giống stand_up: nhiều firmware chỉ nhận mã inner (027,026,…) — thử số trước tên chữ.
        user_first = [config.ROBOT_SIT_ACTION] if config.ROBOT_SIT_ACTION else []
        numeric_sit = (
            config.sit_numeric_fallback() if config.ROBOT_SIT_TRY_NUMERIC else []
        )
        safe_names = [
            "sit_down",
            "sit",
            "squat",
            "SquatDown",
            "Squat",
            "SitDown",
            "sitdown",
        ]

        for n in user_first + numeric_sit + safe_names:
            if n and n not in seen:
                seen.add(n)
                ordered.append(n)
        if await self._try_play_inner_actions(ordered):
            self.pose_state = "sitting"
            return
        if await self._try_behavior_names(ordered):
            self.pose_state = "sitting"
            return
        raise RuntimeError(
            "sit_down: không chạy được inner action hay StartBehavior. "
            "GET /robot/behaviors → ROBOT_SIT_ACTION=id. "
            "Chỉnh ROBOT_SIT_NUMERIC_CSV (vd. 026,027) hoặc ROBOT_SIT_TRY_NUMERIC=false; "
            "ROBOT_SIT_TRY_027=false nếu 027 gây ngã."
        )

    async def stand_up(self):
        # Nhiều firmware Alpha Mini: đứng từ squat = mã số (028…) hiệu quả hơn tên chữ "stand".
        from_sitting = getattr(self, "pose_state", None) == "sitting"
        # Trường hợp từ "ngồi" -> "đứng" là nhạy nhất:
        # nếu gọi stop() ngay có thể làm robot tụt lưng trước rồi mới kịp đứng.
        if not from_sitting:
            try:
                await self.stop()
            except Exception:
                pass
        try:
            settle = max(0.15, float(config.ROBOT_STAND_SETTLE_SEC))
        except (TypeError, ValueError):
            settle = 0.75
        # Nếu vừa chuyển từ ngồi, tăng thời gian chờ trước khi chơi action "đứng"
        # để giảm tình trạng đứng lên khi robot chưa ổn định hoàn toàn.
        if from_sitting:
            try:
                settle = max(settle, float(config.ROBOT_STAND_FROM_SITTING_SETTLE_SEC))
            except Exception:
                pass
        await asyncio.sleep(settle)

        seen: set[str] = set()
        ordered: list[str] = []
        user_first = [config.ROBOT_STAND_ACTION] if config.ROBOT_STAND_ACTION else []
        numeric_stand = (
            config.stand_numeric_fallback() if config.ROBOT_STAND_TRY_NUMERIC else []
        )
        avoid_numeric: set[str] = set()
        if from_sitting:
            try:
                avoid_numeric = {
                    x.strip()
                    for x in str(config.ROBOT_STAND_FROM_SITTING_AVOID_NUMERIC_CSV).split(",")
                    if x.strip()
                }
            except Exception:
                avoid_numeric = {"028"}
            numeric_stand = [x for x in numeric_stand if x not in avoid_numeric]
        # Khi đang ở tư thế ngồi, tránh dùng một số tên "stand" (map sang động tác cứng hơn).
        if from_sitting:
            # Chỉ thử tên "get_up" ít "cứng" hơn so với stand/stand_up.
            safe_names = ["get_up", "GetUp"]
            user_first = [n for n in user_first if n not in ("stand", "stand_up", "StandUp")]
        else:
            # Thử get_up / stand_up trước; để "stand" cuối — một số firmware map "stand" -> bước/giật lạ ("chạy be").
            safe_names = [
                "get_up",
                "GetUp",
                "stand_up",
                "StandUp",
                "SquatUp",
                "squat_up",
                "stand",
            ]

        post = 0.25
        if from_sitting:
            try:
                post = float(config.ROBOT_STAND_POST_STABILIZE_SEC)
            except Exception:
                post = 0.25

        # Phase 1: từ tư thế ngồi → ưu tiên "get_up" (ít cứng hơn).
        # Nếu cần thêm lực/đà để lên hẳn: chạy phase 2 ngay sau đó.
        if from_sitting:
            for n in user_first + safe_names:
                if n and n not in seen:
                    seen.add(n)
                    ordered.append(n)

            phase1_ok = False
            if await self._try_play_inner_actions(ordered):
                phase1_ok = True
            elif await self._try_behavior_names(ordered):
                phase1_ok = True

            if phase1_ok:
                # Chờ để robot "leo" lên tư thế, tránh bị lật ngược khi vừa dậy.
                if post > 0:
                    await asyncio.sleep(post)

                if config.ROBOT_STAND_FROM_SITTING_PHASE2_ENABLE:
                    try:
                        phase2_settle = max(0.0, float(config.ROBOT_STAND_FROM_SITTING_PHASE2_SETTLE_SEC))
                    except Exception:
                        phase2_settle = 0.20
                    if phase2_settle > 0:
                        await asyncio.sleep(phase2_settle)

                    # Phase 2: cố hoàn tất tư thế đứng rõ ràng hơn.
                    phase2_ordered: list[str] = []
                    for n in ("stand_up", "StandUp", "SquatUp", "squat_up"):
                        if n not in phase2_ordered:
                            phase2_ordered.append(n)
                    # numeric fallback (đã lọc avoid_numeric phía trên).
                    for n in numeric_stand:
                        if n and n not in phase2_ordered:
                            phase2_ordered.append(n)

                    if await self._try_play_inner_actions(phase2_ordered) or await self._try_behavior_names(
                        phase2_ordered
                    ):
                        # Chỉ set standing khi phase 2 thành công.
                        if post > 0:
                            await asyncio.sleep(post)
                        self.pose_state = "standing"
                        return

                # Nếu phase 2 thất bại, vẫn thử fallback numeric từ phase 1 + numeric.
                ordered_all = list(ordered)
                seen_all = set(ordered_all)
                for n in numeric_stand:
                    if n and n not in seen_all:
                        seen_all.add(n)
                        ordered_all.append(n)
                if await self._try_play_inner_actions(ordered_all) or await self._try_behavior_names(
                    ordered_all
                ):
                    if post > 0:
                        await asyncio.sleep(post)
                    self.pose_state = "standing"
                    return

            # Phase 1 thất bại → vẫn thử fallback numeric (đã lọc avoid_numeric).
            ordered_all = list(ordered)
            seen_all = set(ordered_all)
            for n in numeric_stand:
                if n and n not in seen_all:
                    seen_all.add(n)
                    ordered_all.append(n)
            if await self._try_play_inner_actions(ordered_all) or await self._try_behavior_names(ordered_all):
                if post > 0:
                    await asyncio.sleep(post)
                self.pose_state = "standing"
                return
        else:
            # Từ squat/khác: nhiều firmware ưu tiên mã số (028…) hơn tên chữ — có thể bật/tắt.
            if getattr(config, "ROBOT_STAND_NONSITTING_NUMERIC_BEFORE_NAMES", True):
                seq_tail = numeric_stand + safe_names
            else:
                seq_tail = safe_names + numeric_stand
            for n in user_first + seq_tail:
                if n and n not in seen:
                    seen.add(n)
                    ordered.append(n)
            if await self._try_play_inner_actions(ordered):
                if post > 0:
                    await asyncio.sleep(post)
                self.pose_state = "standing"
                return
            if await self._try_behavior_names(ordered):
                if post > 0:
                    await asyncio.sleep(post)
                self.pose_state = "standing"
                return

        raise RuntimeError(
            "stand: không chạy được inner action hay StartBehavior. "
            "GET /robot/behaviors (custom_actions) → ROBOT_STAND_ACTION=id. "
            "Chỉnh ROBOT_STAND_NUMERIC_CSV (vd. 028,026) hoặc ROBOT_STAND_TRY_NUMERIC=false."
        )


def _pick_device_address(devices: list) -> str | None:
    """Chọn IPv4 từ danh sách SDK: lọc theo ROBOT_DISCOVER_NAME_SUBSTR nếu có, không thì ưu tên Alpha/Mini/UBTECH."""
    if not devices:
        return None
    substr = (os.getenv("ROBOT_DISCOVER_NAME_SUBSTR") or "").strip().lower()
    rows: list[tuple[str, str]] = []
    for d in devices:
        addr = (getattr(d, "address", "") or "").strip()
        if not addr:
            continue
        name = (getattr(d, "name", "") or "").strip()
        rows.append((name, addr))
    if not rows:
        return None
    if substr:
        for name, addr in rows:
            if substr in name.lower():
                return addr
    best_addr: str | None = None
    best_score = -1
    for name, addr in rows:
        nl = name.lower()
        sc = 0
        for kw in ("alpha", "mini", "ubtech", "ubt"):
            if kw in nl:
                sc += 5
        if sc > best_score:
            best_score, best_addr = sc, addr
    if best_addr is not None and best_score > 0:
        return best_addr
    return rows[0][1]


def _persist_robot_ip_to_dotenv(new_ip: str) -> None:
    if not getattr(config, "ROBOT_PERSIST_DISCOVERED_IP", True):
        return
    path = Path(__file__).resolve().parent / ".env"
    if not path.is_file():
        return
    try:
        raw = path.read_text(encoding="utf-8-sig")
        if re.search(r"(?m)^\s*ROBOT_IP\s*=", raw):
            raw2 = re.sub(r"(?m)^\s*ROBOT_IP\s*=.*$", "ROBOT_IP=" + new_ip.strip(), raw, count=1)
        else:
            raw2 = raw.rstrip() + "\nROBOT_IP=" + new_ip.strip() + "\n"
        path.write_text(raw2, encoding="utf-8-sig")
        log.info("Đã ghi ROBOT_IP=%s vào .env (ROBOT_PERSIST_DISCOVERED_IP)", new_ip.strip())
    except OSError as e:
        log.warning("Không ghi được ROBOT_IP vào .env: %s", e)


async def _lan_robot_connect_candidates() -> list[str]:
    """Thứ tự: quét LAN (nếu bật) → thêm ROBOT_IP trong config. Không trùng IP."""
    out: list[str] = []
    seen: set[str] = set()

    def add(ip: str) -> None:
        ip = (ip or "").strip()
        if ip and ip not in seen:
            seen.add(ip)
            out.append(ip)

    if getattr(config, "ROBOT_AUTO_DISCOVER", False):
        try:
            from mini import mini_sdk

            _set_robot_type_from_config()
            tout = max(2, int(float(getattr(config, "ROBOT_DISCOVER_TIMEOUT_SEC", 8) or 8)))
            devices = await mini_sdk.get_device_list(tout)
            picked = _pick_device_address(list(devices or []))
            if picked:
                add(picked)
                log.info(
                    "ROBOT_AUTO_DISCOVER: %d thiết bị trên LAN → ưu thử IP %s",
                    len(devices or []),
                    picked,
                )
            else:
                log.info("ROBOT_AUTO_DISCOVER: get_device_list trả rỗng hoặc không có địa chỉ")
        except asyncio.CancelledError as e:
            # Python 3.11+/3.13 can raise CancelledError from SDK sleep/scan internals.
            # Don't let reconnect/status requests crash with 500; fall back to TCP sweep/config IP.
            log.warning("ROBOT_AUTO_DISCOVER: quét LAN bị hủy — fallback TCP sweep/config IP (%s)", e)
        except Exception as e:
            log.warning("ROBOT_AUTO_DISCOVER: quét LAN lỗi — %s", e)

    if not out and getattr(config, "ROBOT_DISCOVER_TCP_SWEEP", True):
        port = int(getattr(config, "ROBOT_PORT", 9090) or 9090)
        timeout_s = max(0.05, float(getattr(config, "ROBOT_DISCOVER_TCP_TIMEOUT_SEC", 0.22) or 0.22))
        max_hosts = max(1, min(254, int(getattr(config, "ROBOT_DISCOVER_TCP_MAX_HOSTS", 254) or 254)))
        concurrency = max(4, min(256, int(getattr(config, "ROBOT_DISCOVER_TCP_CONCURRENCY", 72) or 72)))
        lan_ip = str(config.detect_lan_ip() or "").strip()
        octets = lan_ip.split(".")
        if len(octets) == 4 and all(x.isdigit() for x in octets):
            prefix = ".".join(octets[:3]) + "."
            self_host = int(octets[3])
            candidates: list[str] = []
            cfg_ip = str(getattr(config, "ROBOT_IP", "") or "").strip()
            if cfg_ip.startswith(prefix):
                candidates.append(cfg_ip)
            for i in range(1, 255):
                if i == self_host:
                    continue
                ip = f"{prefix}{i}"
                if ip not in candidates:
                    candidates.append(ip)
            candidates = candidates[:max_hosts]

            sem = asyncio.Semaphore(concurrency)

            async def _is_open(ip: str) -> str | None:
                async with sem:
                    try:
                        conn = asyncio.open_connection(ip, port)
                        reader, writer = await asyncio.wait_for(conn, timeout=timeout_s)
                        writer.close()
                        try:
                            await writer.wait_closed()
                        except Exception:
                            pass
                        return ip
                    except Exception:
                        return None

            hits = await asyncio.gather(*(_is_open(ip) for ip in candidates))
            found = [ip for ip in hits if ip]
            for ip in found:
                add(ip)
            log.info(
                "ROBOT_AUTO_DISCOVER_TCP: quét %d host trong %s0/24, cổng %s → thấy %d IP mở",
                len(candidates),
                prefix,
                port,
                len(found),
            )
        else:
            log.warning("ROBOT_AUTO_DISCOVER_TCP: bỏ qua vì detect_lan_ip không hợp lệ: %r", lan_ip)
    add(str(getattr(config, "ROBOT_IP", "") or "").strip())
    return out


def _refresh_audio_url() -> None:
    """
    Called at the start of every connect_robot() so ROBOT_AUDIO_PUBLIC_URL
    always matches the current LAN IP, even after a network change.
    Skips update if user has hardcoded the value in .env.
    """
    env_val = os.getenv("ROBOT_AUDIO_PUBLIC_URL", "").strip().rstrip("/")
    if env_val:
        return  # user pinned it — respect that
    from config import detect_lan_ip
    port = str(getattr(config, "SERVER_PORT", 8000))
    new_url = f"http://{detect_lan_ip()}:{port}"
    if config.ROBOT_AUDIO_PUBLIC_URL != new_url:
        config.ROBOT_AUDIO_PUBLIC_URL = new_url
        log.info("Auto-updated ROBOT_AUDIO_PUBLIC_URL → %s", new_url)
async def connect_robot():
    global robot, _TAKE_PICTURE_ENTER_PROGRAM_RETRIED_THIS_SESSION, _LAST_ROBOT_CONNECT_ERROR
    _refresh_audio_url()   # keep audio URL in sync with current LAN IP
    if not config.ROBOT_ENABLED:
        log.info("🤖 Robot mode: OFFLINE (mock)")
        _LAST_ROBOT_CONNECT_ERROR = None
        return
    tries = max(1, int(getattr(config, "ROBOT_CONNECT_RETRIES", 3)))
    delay = float(getattr(config, "ROBOT_CONNECT_RETRY_DELAY_SEC", 2.5))
    last_err: Exception | None = None
    for attempt in range(1, tries + 1):
        try:
            candidates = await _lan_robot_connect_candidates()
        except asyncio.CancelledError as e:
            log.warning("Lấy danh sách IP robot bị hủy; dùng ROBOT_IP cấu hình (%s)", e)
            candidates = [str(getattr(config, "ROBOT_IP", "") or "").strip()]
        if not candidates:
            log.warning("Không có IP để thử (ROBOT_IP trống và/hoặc discovery trống)")
            _LAST_ROBOT_CONNECT_ERROR = "no candidate IP (set ROBOT_IP or enable ROBOT_AUTO_DISCOVER)"
            robot = None
            return
        for ip_try in candidates:
            try:
                robot = AlphaMiniClient(ip_try)
                await robot.connect()
                log.info("🤖 Robot connected: %s (attempt %s/%s)", ip_try, attempt, tries)
                if ip_try != str(getattr(config, "ROBOT_IP", "") or "").strip():
                    config.ROBOT_IP = ip_try
                _persist_robot_ip_to_dotenv(ip_try)
                _TAKE_PICTURE_ENTER_PROGRAM_RETRIED_THIS_SESSION = False
                _LAST_ROBOT_CONNECT_ERROR = None
                return
            except Exception as e:
                last_err = e
                robot = None
                _LAST_ROBOT_CONNECT_ERROR = str(e)
                log.warning(
                    "⚠️ Robot connect %s attempt %s/%s failed: %s",
                    ip_try,
                    attempt,
                    tries,
                    e,
                )
        if attempt < tries:
            await asyncio.sleep(delay)
    log.warning("⚠️ Robot connect failed sau %s lần: %s — chạy mock mode", tries, last_err)
    robot = None
    if last_err is not None:
        _LAST_ROBOT_CONNECT_ERROR = str(last_err)


def robot_sdk_session_ok() -> bool:
    """Khớp điều kiện chụp ảnh / lệnh: có client và `connect()` đã thành công."""
    return bool(robot and getattr(robot, "connected", False))


async def reconnect_robot_if_ws_dead():
    """Robot ngủ / mất WiFi → WS đứt nhưng `robot` vẫn khác None → SDK báo Client not connected."""
    global robot
    if not config.ROBOT_ENABLED or robot is None:
        return
    try:
        from mini.channels.websocket_client import ubt_websocket

        if ubt_websocket().alive:
            return
    except Exception as e:
        log.warning(f"robot ws check: {e}")
        return
    log.warning("Robot WebSocket đã đứt — đang kết nối lại…")
    try:
        await robot.disconnect()
    except Exception:
        pass
    robot = None
    await connect_robot()


async def ensure_robot_for_commands() -> None:
    """Giống camera: WS đứt hoặc chưa có client → thử reconnect / connect_robot."""
    if not getattr(config, "ROBOT_ENABLED", False):
        return
    await reconnect_robot_if_ws_dead()
    if robot is None:
        await connect_robot()


async def robot_say(text: str):
    global _last_robot_say_text, _last_robot_say_ts
    t = (text or "").strip()
    if not t:
        return
    now = time.monotonic()
    dedup_sec = float(getattr(config, "ROBOT_TTS_DEDUP_SEC", 3.5) or 3.5)
    if t == _last_robot_say_text and (now - _last_robot_say_ts) < max(0.0, dedup_sec):
        log.info("🔇 robot_say(): bỏ qua câu trùng trong %.2fs: %r", dedup_sec, t[:80])
        return
    _last_robot_say_text = t
    _last_robot_say_ts = now
    if robot:
        try:
            # Log ASCII-safe preview để biết payload TTS thực sự là gì.
            preview = t[:80]
            try:
                preview_esc = preview.encode("unicode_escape", "backslashreplace").decode(
                    "ascii"
                )
            except Exception:
                preview_esc = str(preview)
            log.info(f"🔊 robot_say(): speak preview={preview_esc!r}")
            async with _robot_tts_lock:
                ok = await robot.say(t)
                log.info(f"🔊 robot_say finished ok={ok}")
        except Exception as e:
            log.warning(f"robot.say() failed: {e}")
    else:
        log.info(f"🔊 [MOCK] Robot nói: {t}")


async def robot_stop_speaking_now() -> None:
    """Dừng TTS/audio hiện tại trên robot (best-effort) để tránh câu mới đè câu cũ."""
    if not robot:
        return
    try:
        from mini import mini_sdk

        async with _robot_tts_lock:
            try:
                await mini_sdk.stop_tts()
            except Exception:
                pass
            try:
                await mini_sdk.stop_audio()
            except Exception:
                pass
        log.info("🔇 robot_stop_speaking_now(): đã gửi stop_tts + stop_audio")
    except Exception as e:
        log.warning("robot_stop_speaking_now() failed: %s", e)


async def _robot_bg(coro):
    try:
        await coro
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.exception("Robot task lỗi (nền): %s", e)


def _mime_for_audio_upload(filename: str | None, content_type: str | None) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct.startswith("audio/"):
        return ct
    name = (filename or "").lower()
    if name.endswith(".wav"):
        return "audio/wav"
    if name.endswith(".webm"):
        return "audio/webm"
    if name.endswith(".mp3"):
        return "audio/mp3"
    if name.endswith(".ogg") or name.endswith(".oga"):
        return "audio/ogg"
    if name.endswith(".flac"):
        return "audio/flac"
    if name.endswith(".m4a"):
        return "audio/mp4"
    return "audio/webm"


def _transcribe_blocking(audio: bytes, mime_type: str) -> str:
    prompt = (
        "Transcribe the speech verbatim. The speaker may use Vietnamese or English. "
        "Output ONLY the spoken text, no quotes, no explanation."
    )
    resp = client.models.generate_content(
        model=config.VOICE_STT_MODEL,
        contents=[
            types.Part.from_bytes(data=audio, mime_type=mime_type),
            types.Part.from_text(text=prompt),
        ],
    )
    raw = (resp.text or "").strip()
    if not raw:
        raise RuntimeError("STT empty response")
    return raw


async def transcribe_audio_upload(upload: UploadFile) -> tuple[str, str]:
    data = await upload.read()
    if len(data) > config.VOICE_MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio quá lớn (>{config.VOICE_MAX_UPLOAD_BYTES} bytes)",
        )
    if len(data) < 256:
        raise HTTPException(status_code=400, detail="File âm thanh quá ngắn")
    mime = _mime_for_audio_upload(upload.filename, upload.content_type)
    try:
        text = await asyncio.wait_for(
            asyncio.to_thread(_transcribe_blocking, data, mime),
            timeout=config.STT_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="STT timeout")
    except HTTPException:
        raise
    except Exception as e:
        log.warning("STT failed: %s", e)
        raise HTTPException(status_code=502, detail=f"STT lỗi: {e}") from e
    if not text.strip():
        raise HTTPException(status_code=400, detail="STT không thu được lời nói (thử ghi âm rõ hơn)")
    return text, mime

# ── OpenClaw file bridge ─────────────────────────────────────────────
async def _openclaw_file_bridge_loop() -> None:
    """
    OpenClaw đang lỗi `exec` (unsupported platform), nên backend sẽ tự polling file:
      C:\\Users\\<user>\\.openclaw\\workspace\\.alphamini_pending_chat.txt
    và gọi đúng luồng xử lý như POST /chat.
    """
    pending_path = Path(config.OPENCLAW_PENDING_CHAT_PATH)
    poll_sec = float(getattr(config, "OPENCLAW_FILE_BRIDGE_POLL_SEC", 0.4))
    debounce_reads = int(getattr(config, "OPENCLAW_FILE_BRIDGE_DEBOUNCE_READS", 2))
    clear_after = bool(getattr(config, "OPENCLAW_FILE_BRIDGE_CLEAR_AFTER", True))
    speak = bool(getattr(config, "OPENCLAW_FILE_BRIDGE_SPEAK", True))

    log.info(
        "🗂️ OpenClaw file bridge enabled path=%s poll=%.2fs debounce_reads=%s clear_after=%s speak=%s",
        str(pending_path),
        poll_sec,
        debounce_reads,
        clear_after,
        speak,
    )

    last_processed_hash: str | None = None
    candidate_hash: str | None = None
    candidate_mtime_ns: int | None = None
    stable_reads = 0
    in_progress = False

    async def _dummy_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    while True:
        try:
            if in_progress:
                await asyncio.sleep(poll_sec)
                continue

            if pending_path.exists():
                data = pending_path.read_bytes()
                if data:
                    try:
                        text = _decode_openclaw_pending_chat(data)
                    except Exception:
                        text = ""

                    if text:
                        stat = pending_path.stat()
                        mtime_ns = getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9))
                        h = hashlib.sha256(data).hexdigest()

                        if h == candidate_hash and mtime_ns == candidate_mtime_ns:
                            stable_reads += 1
                        else:
                            candidate_hash = h
                            candidate_mtime_ns = mtime_ns
                            stable_reads = 0

                        # Đợi thêm vài vòng để chắc chắn nội dung đã ổn định.
                        if stable_reads >= max(1, debounce_reads - 1) and h != last_processed_hash:
                            in_progress = True
                            try:
                                # Tạo Request giả để tận dụng cùng luồng xử lý như POST /chat.
                                scope = {
                                    "type": "http",
                                    "method": "POST",
                                    "path": "/file-bridge",
                                    "headers": [(b"user-agent", b"openclaw-file-bridge")],
                                    "client": ("openclaw", 0),
                                }
                                dummy_request = Request(scope, _dummy_receive)
                                resp = await process_chat_message(
                                    text, dummy_request, speak=speak, transcript=None
                                )
                                _write_openclaw_last_reply(resp.reply)

                                last_processed_hash = h
                                if clear_after:
                                    # Chỉ clear nếu file không bị ghi thêm trong khi đang xử lý.
                                    if pending_path.exists() and pending_path.stat().st_mtime_ns == candidate_mtime_ns:
                                        pending_path.write_text("", encoding="utf-8")
                            finally:
                                in_progress = False
                                candidate_hash = None
                                candidate_mtime_ns = None
                                stable_reads = 0
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("OpenClaw file bridge loop error: %s", e)

        await asyncio.sleep(poll_sec)


# ── Lifespan ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🚀 Alpha Mini Server đang khởi động...")
    _ensure_tts_cache_dir()
    # Không await connect_robot() ở đây: mỗi lần thử robot ~10s × ROBOT_CONNECT_RETRIES
    # → trình duyệt mở https://127.0.0.1/ sớm sẽ ERR_CONNECTION_REFUSED. Chạy kết nối robot nền.
    robot_connect_task = asyncio.create_task(connect_robot())
    log.info(
        "✅ Web/API sẵn sàng — robot đang kết nối nền (cổng %s). Trang điều khiển: /control hoặc /ui",
        config.SERVER_PORT,
    )

    bridge_task = None
    if getattr(config, "OPENCLAW_FILE_BRIDGE_ENABLED", False):
        bridge_task = asyncio.create_task(_openclaw_file_bridge_loop())

    yield
    log.info("👋 Server đang tắt...")

    robot_connect_task.cancel()
    try:
        await robot_connect_task
    except asyncio.CancelledError:
        pass

    if bridge_task:
        bridge_task.cancel()
        try:
            await bridge_task
        except asyncio.CancelledError:
            pass

    if robot:
        try:
            await robot.disconnect()
        except Exception:
            pass

# ── FastAPI app ───────────────────────────────────────────
app = FastAPI(
    title="Alpha Mini Server",
    description="Server kết nối OpenClaw ↔ Gemini AI ↔ Robot Alpha Mini",
    version="1.0.0",
    lifespan=lifespan
)

_static_dir = Path(__file__).resolve().parent / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


def _load_robot_control_html() -> str:
    path = _static_dir / "control.html"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return (
        "<!DOCTYPE html><html lang=\"vi\"><head><meta charset=\"utf-8\"/><title>Alpha Mini</title></head>"
        "<body style=\"font-family:system-ui;padding:1.5rem\">"
        "<p>Không tìm thấy <code>static/control.html</code> cạnh <code>server.py</code>. "
        "Hãy đồng bộ đủ thư mục repo AlphaMiniServer.</p></body></html>"
    )


ROBOT_CONTROL_HTML = _load_robot_control_html()


def _cors_allow_origins() -> list[str]:
    raw = (getattr(config, "CORS_ALLOW_ORIGINS", "") or "").strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    return [
        "https://127.0.0.1:18789",
        "https://localhost:18789",
        "http://127.0.0.1:18789",
        "http://localhost:18789",
    ]


_cors_origins = _cors_allow_origins()
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )


async def require_skill_token(
    x_alphamini_token: str | None = Header(default=None, alias="X-Alphamini-Token"),
):
    """Optional: set ALPHAMINI_SKILL_TOKEN in .env — then POST /chat, GET /robot/trigger, POST /robot/reconnect require header."""
    expected = (os.getenv("ALPHAMINI_SKILL_TOKEN") or "").strip()
    if not expected:
        return
    if (x_alphamini_token or "").strip() != expected:
        raise HTTPException(status_code=401, detail="invalid skill token")


# ── Models ────────────────────────────────────────────────
class ChatRequest(BaseModel):
    text: str
    # False: chỉ trả text (web/app tự TTS). True: robot phát qua StartPlayTTS (nếu bật config).
    speak: bool = Field(default=True)

class ChatResponse(BaseModel):
    reply: str
    robot_online: bool
    action_detected: bool
    # Có khi lệnh robot chạy đồng bộ (sit/stand/…) — OpenClaw đọc được lỗi thực tế.
    robot_action_ok: bool | None = None
    robot_action_error: str | None = None
    transcript: str | None = None


class UsbWifiProvisionRequest(BaseModel):
    ssid: str
    password: str = ""


# Lệnh chạy đồng bộ (await xong mới trả /chat) — tránh bị _cancel_pending_robot_intent_task() hủy khi có tin tiếp theo (OpenClaw hay gửi 2 lần).
# o_i_i_show: nếu chạy nền, vừa trả OK vừa dễ bị hủy / lỗi im lặng — chạy đồng bộ (client chờ lâu hơn, O_I_I_RUN_SEC có thể rút ngắn).
# mixi_show / quy_khoi_show / play_audio vẫn nền (quá dài); có thể nâng cấp tương tự sau.
_SYNC_EXECUTE_ACTIONS = frozenset({
    "turn_left",
    "turn_right",
    "walk_forward",
    "stop",
    "greet",
    "speak_text",
    "dance",
    "sit_down",
    "sit_then_stand",
    "stand",
    "o_i_i_show",
})

# ── Routes ────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "server": "Alpha Mini Server",
        "version": "1.0.0",
        "endpoints": {
            "chat": "/chat",
            "voice_chat": "/voice/chat",
            "control_web": "GET /control hoặc /ui — giao diện web điều khiển robot (ROBOT_AUTO_DISCOVER: quét LAN, không cần IP mắt robot)",
            "robot_camera_frame_jpeg": "GET /robot/camera/frame",
            "robot_diagnose_tcp": "GET /robot/diagnose — thử TCP tới ROBOT_IP:ROBOT_PORT (không cần SDK đã connect)",
            "robot_music_diagnostics": "GET /robot/music — liệt kê MP3 + URL robot dùng; ?probe=1 để thử tải (chẩn đoán LAN/TLS)",
        },
    }


@app.get("/control", response_class=HTMLResponse)
@app.get("/ui", response_class=HTMLResponse)
async def robot_control_page():
    """Trang web: trạng thái, camera, lệnh /robot/trigger, chat (cần token nếu server bật ALPHAMINI_SKILL_TOKEN)."""
    return HTMLResponse(
        ROBOT_CONTROL_HTML,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


@app.get("/status")
async def status():
    sdk_ok = robot_sdk_session_ok()
    ws_alive: bool | None = None
    if sdk_ok:
        try:
            from mini.channels.websocket_client import ubt_websocket

            ws_alive = bool(ubt_websocket().alive)
        except Exception:
            ws_alive = None
    # robot_online = phiên SDK đã connect (khớp lệnh). robot_ws_alive chỉ phụ chẩn đoán —
    # từng bản SDK/firmware báo alive=false dù vẫn điều khiển được → không gộp vào robot_online (tránh false offline).
    robot_online = sdk_ok
    return {
        "server"      : "running",
        "voice_stt"   : {"model": config.VOICE_STT_MODEL, "path": "/voice/chat"},
        "robot_enabled": config.ROBOT_ENABLED,
        "robot_auto_discover": bool(getattr(config, "ROBOT_AUTO_DISCOVER", False)),
        "robot_persist_discovered_ip": bool(getattr(config, "ROBOT_PERSIST_DISCOVERED_IP", False)),
        "robot_online": robot_online,
        "robot_sdk_connected": sdk_ok,
        "robot_ws_alive": ws_alive,
        "robot_ip"    : config.ROBOT_IP,
        "robot_type"  : config.ROBOT_TYPE,
        "robot_tts"   : {
            "speak_replies": config.ROBOT_SPEAK_REPLIES,
            "infer_from_phrases": config.ROBOT_SPEAK_FROM_PHRASES,
            "mode": config.ROBOT_TTS_MODE,
            "http_engine": config.ROBOT_TTS_HTTP_ENGINE,
            "audio_public_url_effective": config.robot_audio_fetch_base_url(),
            "audio_public_url_set": bool((config.robot_audio_fetch_base_url() or "").strip()),
            "edge_voice": config.EDGE_TTS_VOICE,
            "edge_rate": config.EDGE_TTS_RATE,
            "edge_pitch": config.EDGE_TTS_PITCH,
            "fpt_voice": config.FPT_AI_TTS_VOICE,
            "fpt_key_set": bool((config.FPT_AI_TTS_API_KEY or "").strip()),
        },
        "model"       : config.GEMINI_MODEL,
        "openclaw_files": {
            "last_reply_file": config.OPENCLAW_LAST_REPLY_PATH,
        },
        "robot_camera": {
            "path_preview_jpeg": "GET /robot/camera/frame",
            "image_fetch_mode": getattr(config, "ROBOT_IMAGE_FETCH_MODE", "auto"),
            "note": "TakePicture: ưu tiên bytes trong response SDK, fallback HTTP picPath.",
        },
        "robot_diagnose": {
            "path": "GET /robot/diagnose",
            "hint": "Khi cùng Wi‑Fi mà robot_offline: xem tcp_ok / tcp_error và tips_vi.",
        },
        "robot_last_connect_error": _LAST_ROBOT_CONNECT_ERROR,
        "robot_music": {
            "list_and_diagnostics": "GET /robot/music",
            "play_file_via_robot": "GET /robot/trigger?cmd=audio&url=<URL encode full MP3>",
            "hint": "ROBOT_AUDIO_PUBLIC_URL = IP LAN máy chạy server (không dùng 127.0.0.1). Chạy sync-lan-env.ps1 sau khi đổi Wi‑Fi.",
        },
    }


@app.get("/robot/state")
async def robot_state():
    """Trạng thái robot gọn cho app (kết nối SDK)."""
    sdk = robot_sdk_session_ok()
    ip = ""
    if robot and getattr(robot, "ip", None):
        ip = str(robot.ip).strip()
    if not ip and getattr(config, "ROBOT_IP", None):
        ip = str(config.ROBOT_IP).strip()
    pose = getattr(robot, "pose_state", None) if robot else None
    return {
        "registered": sdk,
        "online": sdk,
        "ip": ip or None,
        "battery": None,
        "mood": pose,
        "robot_type": str(getattr(config, "ROBOT_TYPE", "") or ""),
    }


@app.get("/connect/diagnose")
async def connect_diagnose():
    """Gộp chẩn đoán nhanh — 1 request cho poll nền (app)."""
    sdk = robot_sdk_session_ok()
    ip = ""
    if robot and getattr(robot, "ip", None):
        ip = str(robot.ip).strip()
    if not ip and getattr(config, "ROBOT_IP", None):
        ip = str(config.ROBOT_IP).strip()
    pose = getattr(robot, "pose_state", None) if robot else None
    return {
        "server": {
            "ok": True,
            "version": str(getattr(config, "GEMINI_MODEL", "") or "alpha-mini"),
            "uptime_s": int(time.monotonic() - _SERVER_MONO_START),
        },
        "robot": {
            "registered": sdk,
            "ip": ip or None,
            "online": sdk,
            "battery": None,
            "mood": pose,
            "robot_type": str(getattr(config, "ROBOT_TYPE", "") or ""),
        },
    }


@app.get("/robot/pose")
async def robot_pose():
    """
    Best-effort tư thế dựa trên suy ra từ lần lệnh gần nhất (SDK hiện không expose trực tiếp standing/sitting).
    """
    return {
        "robot_online": robot_sdk_session_ok(),
        "pose_state": getattr(robot, "pose_state", None) if robot else None,
        "pose_confidence": "inferred_from_last_action",
    }


@app.get("/robot/camera/frame")
async def robot_camera_frame(b64: bool = Query(default=False)):
    """
    JPEG một khung từ camera robot (chụp qua SDK + tải picPath).
    Có throttle theo ROBOT_CAMERA_POLL_MIN_SEC — nhiều request trong khoảng đó trả ảnh cache.
    """
    global _ROBOT_FRAME_CACHE, _ROBOT_FRAME_TS
    interval = max(0.5, float(getattr(config, "ROBOT_CAMERA_POLL_MIN_SEC", 2.0) or 2.0))
    now = time.monotonic()
    def _ok_payload(raw: bytes, cached: str, stale: str | None = None, err_kind: str | None = None):
        if b64:
            return {
                "ok": True,
                "image_b64": base64.b64encode(raw).decode("ascii"),
                "cached": cached == "1",
                "stale": stale == "1",
                "error_kind": err_kind,
                "poll_sec": interval,
            }
        headers = {
            "Cache-Control": "no-store",
            "X-Robot-Camera-Cached": cached,
            "X-Robot-Camera-Poll-Sec": f"{interval:.2f}",
        }
        if stale is not None:
            headers["X-Robot-Camera-Stale"] = stale
        if err_kind:
            headers["X-Robot-Camera-Err"] = err_kind
        return Response(content=raw, media_type="image/jpeg", headers=headers)

    if _ROBOT_FRAME_CACHE is not None and (now - _ROBOT_FRAME_TS) < interval:
        return _ok_payload(_ROBOT_FRAME_CACHE, cached="1")
    raw_img, err = await _robot_capture_image_bytes()
    if raw_img:
        _ROBOT_FRAME_CACHE = raw_img
        _ROBOT_FRAME_TS = time.monotonic()
        return _ok_payload(raw_img, cached="0")
    if _ROBOT_FRAME_CACHE is not None:
        return _ok_payload(
            _ROBOT_FRAME_CACHE,
            cached="1",
            stale="1",
            err_kind=str((err or {}).get("kind", "unknown")),
        )
    k = (err or {}).get("kind", "")
    if k == "robot_disabled":
        raise HTTPException(
            status_code=503,
            detail="Chế độ robot tắt (ROBOT_ENABLED=false trong .env).",
        )
    if k == "robot_offline":
        raise HTTPException(
            status_code=503,
            detail="Robot chưa kết nối. Kiểm tra ROBOT_IP, Wi‑Fi robot, rồi POST /robot/connect hoặc khởi động lại server.",
        )
    if k == "sdk_error":
        raise HTTPException(status_code=503, detail=f"SDK take_picture_immediately lỗi: {err.get('message', '')}")
    if k == "sdk_transport":
        raise HTTPException(
            status_code=503,
            detail=(
                f"Lệnh chụp không nhận phản hồi hợp lệ từ robot ({err.get('resultType')}). "
                "Thử POST /robot/connect hoặc khởi động lại server."
            ),
        )
    if k == "no_picture":
        raise HTTPException(status_code=503, detail=_no_picture_http_detail(err))
    if k == "sdk_no_data":
        raise HTTPException(
            status_code=503,
            detail=(err.get("message") or "SDK không trả bytes ảnh trong response."),
        )
    if k == "download_failed":
        tried = ((err or {}).get("urls_tried") or [])[:24]
        raise HTTPException(
            status_code=502,
            detail={
                "message": err.get("message")
                or "Đã chụp trên robot nhưng không tải được file ảnh qua HTTP.",
                "picPath": err.get("picPath"),
                "urls_tried": tried,
                "hint": "Thử .env: ROBOT_IMAGE_URL_TEMPLATE=http://{ip}:8080{path} hoặc ROBOT_FILE_HTTP_PORTS=8080,8888; .\\diagnose-robot-http.ps1",
            },
        )
    raise HTTPException(status_code=502, detail=str(err))


@app.get("/robot/diagnose")
async def robot_diagnose():
    """
    Không cần SDK đã connect: thử TCP tới ROBOT_IP:ROBOT_PORT (mặc định 9090, WebSocket UBTECH).
    Giúp phân biệt 'sai IP / robot ngủ / firewall' vs 'TCP OK nhưng SDK/ROBOT_TYPE lỗi'.
    """
    if not config.ROBOT_ENABLED:
        return {
            "robot_enabled": False,
            "detail": "ROBOT_ENABLED=false — bật trong .env và restart server.",
        }
    host = (config.ROBOT_IP or "").strip()
    port = int(getattr(config, "ROBOT_PORT", 9090) or 9090)
    rtype = (getattr(config, "ROBOT_TYPE", "mini") or "mini").strip()
    tips_vi = [
        "Cùng mạng = PC và robot cùng Wi‑Fi, IPv4 cùng dải (vd. robot 192.168.0.50 → PC phải 192.168.0.x). Chạy ipconfig; ping có thể bị chặn — ưu tiên tcp_ok và IP trên app UBTECH.",
        "Robot phát hotspot: PC phải kết nối đúng hotspot đó — không được để PC chỉ nối Ethernet sang mạng khác.",
        f".env: ROBOT_IP phải trùng IP robot (hiện tại: {host or 'THIẾU'}).",
        f"Firewall Windows: cho phép Python / cổng TCP {port} (hoặc tắt tạm để thử).",
        "Ping được nhưng TCP timeout: bật robot khỏi chế độ ngủ; thử ROBOT_TYPE=edu nếu firmware quốc tế.",
        "Đổi Wi‑Fi: .\\sync-lan-env.ps1 rồi restart server (ROBOT_AUDIO_PUBLIC_URL).",
    ]
    if not host:
        return {
            "robot_enabled": True,
            "robot_ip": "",
            "robot_port": port,
            "robot_type": rtype,
            "tcp_ok": False,
            "tcp_error": "missing ROBOT_IP",
            "tips_vi": tips_vi,
        }
    tcp_ok = False
    tcp_error: str | None = None
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=6.0,
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        tcp_ok = True
    except asyncio.TimeoutError:
        tcp_error = "timeout — không mở được TCP (sai IP, robot tắt/ngủ, khác mạng, hoặc firewall chặn)."
    except OSError as e:
        tcp_error = str(e)
    except Exception as e:
        tcp_error = str(e)
    return {
        "robot_enabled": True,
        "robot_ip": host,
        "robot_port": port,
        "robot_type": rtype,
        "tcp_ok": tcp_ok,
        "tcp_error": tcp_error,
        "tips_vi": tips_vi,
        "note": "tcp_ok chỉ báo cổng TCP phản hồi; WebSocket SDK vẫn có thể lỗi nếu sai ROBOT_TYPE hoặc firmware.",
        "last_sdk_connect_error": _LAST_ROBOT_CONNECT_ERROR,
    }


@app.get("/robot/scan")
async def robot_scan(timeout: int = 6):
    try:
        from mini import mini_sdk

        _set_robot_type_from_config()
        devices = await mini_sdk.get_device_list(timeout)
        results = []
        for d in devices:
            results.append({
                "name": getattr(d, "name", ""),
                "address": getattr(d, "address", ""),
                "port": getattr(d, "port", -1),
                "service_type": getattr(d, "s_type", ""),
                "server": getattr(d, "server", ""),
            })
        return {"count": len(results), "devices": results}
    except Exception as e:
        log.error(f"robot scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Robot scan lỗi: {e}")

@app.post("/robot/connect")
async def robot_connect(timeout: int = 6):
    global robot, _LAST_ROBOT_CONNECT_ERROR
    candidates: list[str] = []
    device_name_by_ip: dict[str, str] = {}

    try:
        from mini import mini_sdk

        _set_robot_type_from_config()
        devices = await mini_sdk.get_device_list(timeout)
        for d in list(devices or []):
            addr = (getattr(d, "address", "") or "").strip()
            if not addr:
                continue
            if addr not in candidates:
                candidates.append(addr)
            name = (getattr(d, "name", "") or "").strip()
            if name:
                device_name_by_ip[addr] = name
        picked = _pick_device_address(list(devices or []))
        if picked and picked in candidates:
            candidates.remove(picked)
            candidates.insert(0, picked)
    except Exception as e:
        log.warning("robot/connect: sdk scan lỗi — %s", e)

    # SDK scan có thể rỗng trên một số Wi-Fi/AP; fallback sang danh sách connect candidates chung.
    if not candidates:
        for ip in await _lan_robot_connect_candidates():
            if ip not in candidates:
                candidates.append(ip)

    if not candidates:
        raise HTTPException(status_code=404, detail="Không quét thấy robot trong LAN")

    last_err: Exception | None = None
    for ip_try in candidates:
        try:
            new_client = AlphaMiniClient(ip_try)
            await new_client.connect()
            robot = new_client
            config.ROBOT_IP = ip_try
            _persist_robot_ip_to_dotenv(ip_try)
            _LAST_ROBOT_CONNECT_ERROR = None
            return {
                "connected": True,
                "robot_ip": robot.ip,
                "device_name": device_name_by_ip.get(ip_try, ""),
                "candidate_count": len(candidates),
            }
        except Exception as e:
            last_err = e
            _LAST_ROBOT_CONNECT_ERROR = str(e)
            continue

    raise HTTPException(
        status_code=500,
        detail=f"Robot connect lỗi: {last_err}" if last_err else "Robot connect lỗi",
    )


@app.post("/robot/wifi/provision-usb")
async def robot_wifi_provision_usb(req: UsbWifiProvisionRequest):
    """
    USB-first provisioning helper:
    - Kiểm tra robot đang cắm ADB
    - Bật Wi-Fi + mở màn hình Wi-Fi settings trên robot
    - Thử lệnh cmd wifi connect-network (nếu firmware Android hỗ trợ)
    """
    ssid = (req.ssid or "").strip()
    password = (req.password or "").strip()
    if not ssid:
        raise HTTPException(status_code=400, detail="Thiếu SSID")

    def _run(cmd: list[str], timeout: int = 12) -> tuple[int, str]:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = ((p.stdout or "") + "\n" + (p.stderr or "")).strip()
        return p.returncode, out

    code, out = _run(["adb", "devices"], timeout=10)
    if code != 0:
        raise HTTPException(status_code=500, detail=f"ADB lỗi: {out}")

    device_id = ""
    for line in out.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("list of devices"):
            continue
        if line.endswith("\tdevice"):
            device_id = line.split("\t")[0].strip()
            break
    if not device_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị ADB. Hãy cắm USB và bật USB debugging.")

    _run(["adb", "-s", device_id, "shell", "svc", "wifi", "enable"])
    _run(["adb", "-s", device_id, "shell", "am", "start", "-a", "android.settings.WIFI_SETTINGS"])

    # Android mới có thể hỗ trợ cmd wifi connect-network; Android 7 có thể không hỗ trợ.
    connect_attempts: list[dict] = []
    if password:
        cmds = [
            ["adb", "-s", device_id, "shell", "cmd", "-w", "wifi", "connect-network", ssid, "wpa2", password],
            ["adb", "-s", device_id, "shell", "cmd", "wifi", "connect-network", ssid, "wpa2", password],
        ]
    else:
        cmds = [
            ["adb", "-s", device_id, "shell", "cmd", "-w", "wifi", "connect-network", ssid, "open", ""],
            ["adb", "-s", device_id, "shell", "cmd", "wifi", "connect-network", ssid, "open", ""],
        ]

    success = False
    for cmd in cmds:
        c, o = _run(cmd)
        connect_attempts.append({"cmd": " ".join(cmd[4:]), "exit_code": c, "output": o[:500]})
        if c == 0 and ("success" in o.lower() or "connected" in o.lower() or not o):
            success = True
            break

    return {
        "ok": True,
        "usb_device": device_id,
        "ssid": ssid,
        "attempted_auto_connect": True,
        "auto_connect_success": success,
        "attempts": connect_attempts,
        "next_step_vi": (
            "Nếu chưa tự kết nối, màn hình Wi-Fi trên robot đã được mở sẵn. "
            "Chỉ cần chạm vào mạng và xác nhận mật khẩu trên robot."
        ),
    }


@app.post("/robot/network/import-usb")
async def robot_network_import_usb():
    """
    Nhập mạng từ điện thoại qua dây USB (USB tethering):
    - Kiểm tra robot đang kết nối ADB
    - Dò interface usb/rndis/eth có IP
    - Test internet cơ bản từ robot
    """

    def _run(cmd: list[str], timeout: int = 12) -> tuple[int, str]:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = ((p.stdout or "") + "\n" + (p.stderr or "")).strip()
        return p.returncode, out

    code, out = _run(["adb", "devices"], timeout=10)
    if code != 0:
        raise HTTPException(status_code=500, detail=f"ADB lỗi: {out}")

    device_id = ""
    for line in out.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("list of devices"):
            continue
        if line.endswith("\tdevice"):
            device_id = line.split("\t")[0].strip()
            break
    if not device_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy robot qua ADB. Hãy cắm USB và bật USB debugging.")

    cmds: list[dict] = []
    c_ip, o_ip = _run(["adb", "-s", device_id, "shell", "ip", "-f", "inet", "addr", "show"])
    cmds.append({"cmd": "ip -f inet addr show", "exit_code": c_ip, "output": o_ip[:800]})
    if c_ip != 0:
        raise HTTPException(status_code=500, detail="Không đọc được network interfaces trên robot.")

    ifaces: list[dict] = []
    cur_name = ""
    for raw in o_ip.splitlines():
        line = raw.strip()
        if not line:
            continue
        if ": " in line and line[0].isdigit():
            cur_name = line.split(": ", 1)[1].split(":", 1)[0].strip()
            continue
        if line.startswith("inet ") and cur_name:
            ip = line.split()[1].split("/", 1)[0]
            if any(k in cur_name.lower() for k in ("rndis", "usb", "eth")):
                ifaces.append({"name": cur_name, "ipv4": ip})

    c_ping, o_ping = _run(["adb", "-s", device_id, "shell", "ping", "-c", "1", "-W", "2", "1.1.1.1"], timeout=8)
    cmds.append({"cmd": "ping -c 1 -W 2 1.1.1.1", "exit_code": c_ping, "output": o_ping[:500]})
    internet_ok = c_ping == 0

    next_step = (
        "Nếu chưa có mạng: trên điện thoại hãy bật USB tethering (chia sẻ mạng qua USB), "
        "giữ điện thoại cắm vào robot bằng cáp data rồi bấm lại."
    )
    if ifaces and not internet_ok:
        next_step = (
            "Robot đã thấy cổng USB nhưng chưa ra Internet. Hãy kiểm tra điện thoại đã bật USB tethering và quyền truy cập mạng."
        )
    if internet_ok:
        next_step = "Robot đã nhận Internet qua USB thành công."

    return {
        "ok": True,
        "usb_device": device_id,
        "usb_ifaces": ifaces,
        "internet_ok": internet_ok,
        "robot_cmds": cmds,
        "next_step_vi": next_step,
    }


@app.get("/robot/behaviors")
async def robot_behaviors():
    """Danh sách action inner + custom (GetActionList) — để chọn ROBOT_SIT_ACTION / STAND."""
    if not robot_sdk_session_ok():
        raise HTTPException(status_code=503, detail="Robot chưa kết nối")
    try:
        from mini import mini_sdk
        from mini.apis.api_action import GetActionList
        from mini import RobotActionType

        inner = await mini_sdk.get_action_list()
        custom: list = []
        try:
            block = GetActionList(True, RobotActionType.CUSTOM)
            result = await block.execute()
            if AlphaMiniClient._is_api_success(result) and len(result) == 2:
                custom = list(getattr(result[1], "actionList", None) or [])
        except Exception as ce:
            log.warning("get_action_list CUSTOM: %s", ce)

        return {
            "behaviors": _action_info_items_to_json(inner),
            "custom_actions": _action_info_items_to_json(custom),
            "inner_count": len(inner or []),
            "custom_count": len(custom or []),
        }
    except Exception as e:
        log.warning(f"get_action_list failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/robot/selftest")
async def robot_selftest():
    if not robot_sdk_session_ok():
        raise HTTPException(status_code=400, detail="Robot chưa kết nối")

    results = {"tts": False, "turn": False, "forward": False}
    errors = {}

    try:
        await robot.say("Xin chao")
        results["tts"] = True
    except Exception as e:
        errors["tts"] = str(e)

    try:
        await robot.turn_left()
        results["turn"] = True
    except Exception as e:
        errors["turn"] = str(e)

    try:
        await robot.walk_forward()
        results["forward"] = True
    except Exception as e:
        errors["forward"] = str(e)

    return {"ok": all(results.values()), "results": results, "errors": errors}


@app.get("/robot/tts_test")
async def robot_tts_test(text: str = "Xin chao!", via: str | None = None):
    """
    Test TTS đồng bộ và trả về ok=true/false (giúp debug vì robot có thể 'im' do âm lượng).
    via=sdk | http | để trống (theo ROBOT_TTS_MODE).
    """
    if not robot_sdk_session_ok():
        raise HTTPException(status_code=400, detail="Robot chưa kết nối")
    v = (via or "").strip().lower()
    if v == "http":
        ok = await robot._say_via_http_audio(text)
        used = "http"
    elif v == "sdk":
        ok = await robot._say_via_sdk(text)
        used = "sdk"
    else:
        ok = await robot.say(text)
        used = config.ROBOT_TTS_MODE
    return {"ok": bool(ok), "text": text, "via": used}


@app.get("/robot/tts_media/{filename}")
async def robot_tts_media(filename: str):
    """Robot tải file MP3 TTS (chỉ tên uuid32 + .mp3)."""
    if not re.fullmatch(r"[a-f0-9]{32}\.mp3", filename, re.IGNORECASE):
        raise HTTPException(status_code=404, detail="Not found")
    path = _TTS_CACHE_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type="audio/mpeg")


async def _probe_robot_music_url(url: str) -> dict:
    """Thử GET từ chính server (giống robot: tải MP3 qua LAN). Bỏ qua verify TLS (cert tự ký)."""
    import aiohttp

    t0 = time.monotonic()
    timeout = aiohttp.ClientTimeout(total=20)
    connector = aiohttp.TCPConnector(ssl=False)
    try:
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.get(url) as resp:
                body = await resp.read()
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                return {
                    "http_status": resp.status,
                    "bytes": len(body),
                    "ok": resp.status == 200 and len(body) >= 64,
                    "elapsed_ms": elapsed_ms,
                    "error": None,
                }
    except Exception as e:
        return {
            "http_status": None,
            "bytes": 0,
            "ok": False,
            "elapsed_ms": int((time.monotonic() - t0) * 1000),
            "error": str(e),
        }


@app.get("/robot/music")
async def robot_music_diagnostics(probe: bool = False):
    """
    Chẩn đoán kết nối `robot_music/`: file có sẵn, URL công khai robot dùng để tải (`ROBOT_AUDIO_PUBLIC_URL`),
    robot đã kết nối SDK hay chưa. Thêm `?probe=1` để server tự GET thử từng URL (kiểm tra TLS/mạng).
    """
    base_raw = (config.ROBOT_AUDIO_PUBLIC_URL or "").strip().rstrip("/")
    base_eff = (config.robot_audio_fetch_base_url() or "").strip().rstrip("/")
    ssl_on = config.server_ssl_cert_key() is not None
    issues: list[str] = []
    if not base_eff:
        issues.append(
            "ROBOT_AUDIO_PUBLIC_URL chưa đặt trong .env — robot không biết URL để tải MP3 từ máy bạn."
        )
    elif base_eff.startswith("https://") and base_raw.startswith("http://"):
        issues.append(
            "Server đang HTTPS: URL robot dùng đã nâng lên https:// (xem robot_audio_fetch_base_url). "
            "Robot phải tải được HTTPS (cert tự ký có thể bị robot từ chối — thử mkcert / cert hợp lệ trên robot)."
        )
    if base_eff and ("127.0.0.1" in base_eff or base_eff.endswith("localhost")):
        issues.append(
            "ROBOT_AUDIO_PUBLIC_URL đang trỏ localhost — robot trên LAN không truy cập được. "
            "Dùng IP LAN máy PC (vd. 192.168.x.x) và chạy sync-lan-env.ps1."
        )

    tracks: list[dict] = []
    try:
        _ROBOT_MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        for p in sorted(_ROBOT_MUSIC_DIR.iterdir()):
            if not p.is_file():
                continue
            low = p.name.lower()
            if low.endswith((".mp3", ".wav", ".m4a", ".aac")):
                pub = f"{base_eff}/robot/music/{p.name}" if base_eff else None
                item: dict = {
                    "filename": p.name,
                    "size_bytes": p.stat().st_size,
                    "public_url": pub,
                }
                if probe and pub:
                    item["probe"] = await _probe_robot_music_url(pub)
                elif probe and not pub:
                    item["probe"] = {"skipped": True, "reason": "no ROBOT_AUDIO_PUBLIC_URL"}
                tracks.append(item)
    except OSError as e:
        issues.append(f"Không đọc được thư mục robot_music: {e}")

    if not tracks:
        issues.append(
            "Chưa có file .mp3/.wav/.m4a/.aac trong robot_music/ — thêm file hoặc kiểm tra tên."
        )

    oii = (os.getenv("O_I_I_LAN_MP3") or "").strip()
    if oii:
        hit = any(t["filename"] == oii for t in tracks)
        if not hit:
            issues.append(
                f"O_I_I_LAN_MP3={oii!r} nhưng không thấy file trùng tên trong robot_music/."
            )

    return {
        "music_dir": str(_ROBOT_MUSIC_DIR.resolve()),
        "robot_online": robot_sdk_session_ok(),
        "robot_enabled": config.ROBOT_ENABLED,
        "robot_ip_config": config.ROBOT_IP,
        "server_port": config.SERVER_PORT,
        "server_https": ssl_on,
        "public_base_env": base_raw or None,
        "public_base_effective": base_eff or None,
        "note_effective_url": (
            "Khi bật ssl/server.crt, http:// trong .env được đổi thành https:// để robot không gọi nhầm HTTP vào cổng TLS."
            if ssl_on
            else None
        ),
        "tracks": tracks,
        "issues": issues,
        "hints": [
            "Robot phát nhạc: SDK play_online_audio(URL) — URL phải là địa chỉ máy PC mà robot ping/tải được.",
            "Thử phát tay: GET /robot/trigger?cmd=audio&url=<URL encode>",
            "Đồng bộ IP: .\\sync-lan-env.ps1 rồi restart server.",
        ],
    }


@app.get("/robot/music/{filename}")
async def robot_public_music(filename: str):
    """
    Robot tải nhạc MP3/WAV qua LAN (play_online_audio).
    Đặt file trong thư mục robot_music/ cùng cấp server.py; .env: ROBOT_AUDIO_PUBLIC_URL + O_I_I_LAN_MP3.
    """
    if not re.fullmatch(
        r"[a-zA-Z0-9][a-zA-Z0-9_.-]*\.(mp3|wav|m4a|aac)$",
        filename,
        re.IGNORECASE,
    ):
        raise HTTPException(status_code=404, detail="Not found")
    path = _ROBOT_MUSIC_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    low = filename.lower()
    if low.endswith(".wav"):
        media = "audio/wav"
    elif low.endswith(".mp3"):
        media = "audio/mpeg"
    else:
        media = "audio/mp4"
    _TTS_MEDIA_LAST_HIT[filename] = time.monotonic()
    return FileResponse(path, media_type=media)


@app.post("/robot/reconnect", dependencies=[Depends(require_skill_token)])
async def robot_reconnect():
    """Kích hoạt lại kết nối SDK (sau khi robot ngủ, đổi WiFi, lỗi WinError 64…)."""
    global robot
    if not config.ROBOT_ENABLED:
        raise HTTPException(status_code=400, detail="ROBOT_ENABLED=false")
    # Avoid forced disconnect when SDK session is already healthy.
    # On some firmware/SDK combos, disconnect() can destabilize the process loop.
    if robot_sdk_session_ok():
        return {
            "ok": True,
            "robot_online": True,
            "ip": config.ROBOT_IP,
        }

    # If we have a stale client object, drop reference and reconnect cleanly.
    robot = None
    try:
        await connect_robot()
    except asyncio.CancelledError as e:
        log.warning("/robot/reconnect bị hủy trong lúc connect_robot: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Reconnect bị hủy tạm thời; thử lại sau 1-2 giây.",
        ) from e
    return {
        "ok": robot_sdk_session_ok(),
        "robot_online": robot_sdk_session_ok(),
        "ip": config.ROBOT_IP,
    }


@app.get("/robot/trigger", dependencies=[Depends(require_skill_token)])
async def robot_trigger(
    cmd: str,
    request: Request,
    behavior: str | None = None,
    url: str | None = None,
):
    """
    Gọi trực tiếp một hành động robot (OpenClaw có thể dùng GET thay vì POST JSON).
    Ví dụ:
      GET /robot/trigger?cmd=dance
      GET /robot/trigger?cmd=dance&behavior=dance_0005
      GET /robot/trigger?cmd=audio&url=https://example.com/song.mp3
    """
    global robot
    peer = request.client.host if request.client else "?"
    log.info(
        f"🎯 /robot/trigger cmd={cmd!r} behavior={behavior!r} url={url!r} client={peer}"
    )
    await ensure_robot_for_commands()
    if not robot_sdk_session_ok():
        raise HTTPException(
            status_code=503,
            detail=(
                "Robot chưa kết nối SDK. Thử POST /robot/connect (quét LAN), POST /robot/reconnect, "
                "kiểm tra ROBOT_IP và Wi‑Fi; GET /status xem robot_sdk_connected / robot_ws_alive."
            ),
        )

    await _cancel_pending_robot_intent_task()

    c = normalize_text(cmd)
    try:
        if c in ("audio", "nhac", "music", "play"):
            if not url or not url.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Thiếu url. Ví dụ: ?cmd=audio&url=https://...",
                )
            ok = await robot.play_online_music(url.strip())
            return {"ok": ok, "action": "play_audio", "url": url.strip()}
        if c in ("mixi", "mixi_show", "an_do_mixi", "ando_mixi"):
            from dances.an_do_mixi_dance import run_mixi_show

            await run_mixi_show()
            return {"ok": True, "action": "mixi_show"}
        if c in ("o_i_i", "o_i_i_show", "oii", "alo vu", "oi_i"):
            from dances.o_i_i_dance import run_o_i_i_show

            na = (request.query_params.get("na_na") or "").strip().lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
            prev_na = os.environ.get("O_I_I_NA_NA_BACKING")
            try:
                if na:
                    os.environ["O_I_I_NA_NA_BACKING"] = "1"
                await run_o_i_i_show()
            finally:
                if na:
                    if prev_na is None:
                        os.environ.pop("O_I_I_NA_NA_BACKING", None)
                    else:
                        os.environ["O_I_I_NA_NA_BACKING"] = prev_na
            return {"ok": True, "action": "o_i_i_show", "na_na_backing": na}
        if c in (
            "quy khoi",
            "tay note",
            "quy khoi tay note",
            "quykhoi",
            "quy_khoi",
            "tay_note",
        ):
            from dances.quy_khoi_tay_note_show import run_quy_khoi_show

            await run_quy_khoi_show()
            return {"ok": True, "action": "quy_khoi_show"}
        if c in ("dance", "nhay", "mua"):
            b = behavior.strip() if behavior else None
            await robot.dance(b)
            label = "dance" + (f":{b}" if b else "")
        elif c in ("left", "trai", "quay trai"):
            await robot.turn_left()
            label = "turn_left"
        elif c in ("right", "phai", "quay phai"):
            await robot.turn_right()
            label = "turn_right"
        elif c in ("forward", "di", "tien", "buoc"):
            await robot.walk_forward()
            label = "walk_forward"
        elif c in ("stop", "dung"):
            _stop_all_choreography_loops()
            await robot.stop()
            label = "stop"
        elif c in ("greet", "chao", "hello"):
            await robot.greet()
            label = "greet"
        elif c in ("sit", "ngoi", "squat", "sit_down"):
            await robot.sit_down()
            label = "sit_down"
        elif c in (
            "stand",
            "stand_up",
            "dung len",
            "dung day",
            "ngoi day",
            "stand up",
        ):
            await robot.stand_up()
            label = "stand"
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Lệnh không hỗ trợ: {cmd}. "
                    "Thử: mixi, dance, left, right, forward, stop, greet, sit, stand, audio (+ url)"
                ),
            )
        return {"ok": True, "action": label}
    except HTTPException:
        raise
    except Exception as e:
        log.warning(f"robot_trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_chat_message(
    text: str,
    request: Request,
    *,
    speak: bool,
    transcript: str | None = None,
) -> ChatResponse:
    if not text.strip():
        raise HTTPException(status_code=400, detail="text không được để trống")

    text_raw = text.strip()
    text = _normalize_openclaw_pending_text(text_raw)
    if text != text_raw:
        log.info(
            "📂 OpenClaw: trich lenh user tu payload tool (%s chars -> %s chars)",
            len(text_raw),
            len(text),
        )

    peer = request.client.host if request.client else "?"
    ua = (request.headers.get("user-agent") or "")[:120]
    log.info(f"📩 chat pipeline from {peer} ua={ua!r} text={text!r}")

    plan = await plan_robot_intent(text)
    action_detected = plan is not None
    log.info(f"🧠 Robot plan: {plan}")

    text_norm = normalize_text(text)
    # Câu múa võ / O I I + na na: ưu tiên câu trả lời nhanh (tránh Gemini).
    is_short_action_cmd = (action_detected and len(text_norm.split()) <= 8) or (
        len(text_norm.split()) <= 8 and _martial_intent_keywords_norm(text_norm)
    ) or (len(text_norm.split()) <= 14 and _wants_o_i_i_choreography(text_norm))

    robot_action_ok: bool | None = None
    robot_action_error: str | None = None

    act = (plan or {}).get("action") if plan else None
    run_sync = bool(plan and act and act in _SYNC_EXECUTE_ACTIONS)

    if plan:
        global _robot_intent_task
        # File-bridge/OpenClaw có thể gửi lệnh ngay lúc server vừa khởi động, khi connect_robot nền chưa xong.
        # Thử kéo kết nối robot lên trước khi kết luận "chưa kết nối" để giảm fail giả cho lệnh speak/greet/sit/stand...
        await ensure_robot_for_commands()
        await _cancel_pending_robot_intent_task()
        if run_sync:
            if not robot:
                robot_action_ok = False
                robot_action_error = "Robot chua ket noi (kiem tra ROBOT_ENABLED / may chu da connect robot)."
            else:
                try:
                    await execute_intent_plan(plan, text)
                    robot_action_ok = True
                except Exception as e:
                    robot_action_ok = False
                    robot_action_error = str(e)
                    log.warning("execute_intent_plan (sync): %s", e)
        else:
            _robot_intent_task = asyncio.create_task(
                _robot_bg(execute_intent_plan(plan, text))
            )

    if is_short_action_cmd:
        if robot_action_ok is False:
            reply = (
                f"Robot khong thuc hien duoc ({robot_action_error or 'loi khong ro'}). "
                "Kiem tra log server; goi GET /robot/behaviors va dat ROBOT_SIT_ACTION / ROBOT_STAND_ACTION trong .env."
            )
        else:
            reply = build_quick_action_reply(text_norm, text)
    else:
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(chat_session.send_message, text),
                timeout=12,
            )
            reply = response.text.strip()
        except asyncio.TimeoutError:
            log.warning("Gemini timeout >12s, returning fallback reply")
            reply = "Minh dang xu ly hoi cham, ban thu lai giup minh nhe."
        except Exception as e:
            log.error(f"Gemini error: {e}")
            reply = "Minh tam thoi gap loi ket noi model, ban thu lai sau nhe."

    reply = (reply or "").strip()
    if not reply:
        # Gemini doi khi tra chuoi rong (sau tool / quota). File bridge OpenClaw can noi dung nay lam last reply.
        reply = build_quick_action_reply(text_norm, text) or "OK, da xu ly."
        log.warning("chat: reply trong -> fallback %r", reply[:120])

    log.info(f"🤖 Tra loi gui client: {reply}")

    inferred = (
        _user_wants_spoken_reply(text) if config.ROBOT_SPEAK_FROM_PHRASES else False
    )
    wants_speak = bool(speak) or inferred
    if _user_wants_silence(text):
        wants_speak = False
        asyncio.create_task(_robot_bg(robot_stop_speaking_now()))
    effective_speak = wants_speak and config.ROBOT_SPEAK_REPLIES
    # `greet` / `speak_text` đã tự TTS trong `execute_intent_plan` → tránh gọi thêm `robot_say(reply)`
    # gây chồng âm/thử giọng liên tục.
    # `dance`: StartBehavior thường trả về ngay khi bắt đầu vũ đạo; `robot_say(reply)` ngay sau đó
    # chiếm loa / dừng nhạc nền gắn trong firmware → không phát nhạc nhảy.
    if run_sync and act in ("greet", "speak_text", "dance"):
        effective_speak = False
    # mixi / quy_khoi / o_i_i: nhạc + vũ đạo dài — tránh TTS đè loa.
    if act in ("mixi_show", "quy_khoi_show", "o_i_i_show"):
        effective_speak = False
    if effective_speak:
        log.info(
            f"🔊 schedule robot_say: req_speak={speak} inferred={bool(inferred)} "
            f"text_len={len(text or '')}"
        )
        # Ưu tiên phần "câu trả lời chính", tránh chỉ đọc câu mở đầu kiểu "Chào bạn...".
        tts_text = (reply or "").strip()
        import re as _re

        # Nếu có markdown bullet list, đọc chính danh sách để trả lời đúng ý user.
        bullet_items = []
        for ln in tts_text.splitlines():
            m = _re.match(r"^\s*[*\-]\s+(.+?)\s*$", ln)
            if m:
                item = m.group(1).strip()
                if item:
                    bullet_items.append(item)
        if bullet_items:
            tts_text = ", ".join(bullet_items[:6])
        else:
            parts = [p.strip() for p in _re.split(r"(?<=[.!?])\s+", tts_text) if p.strip()]
            if parts:
                def _is_lead_in_sentence(s: str) -> bool:
                    s_norm = normalize_text(s)
                    return s_norm.startswith(
                        (
                            "chao ban",
                            "xin chao",
                            "hello",
                            "ok",
                            "duoc roi",
                        )
                    )
                # Bỏ câu chào đầu nếu còn câu sau mang nội dung trả lời.
                if len(parts) > 1 and _is_lead_in_sentence(parts[0]):
                    parts = parts[1:]
                tts_text = parts[0]
        # Dọn markdown còn sót và giới hạn độ dài cho TTS firmware.
        tts_text = _re.sub(r"[`*_#]", "", tts_text).strip()
        if len(tts_text) > 220:
            tts_text = tts_text[:220].rstrip()
        asyncio.create_task(_robot_bg(robot_say(tts_text)))

    return ChatResponse(
        reply=reply,
        robot_online=robot_sdk_session_ok(),
        action_detected=action_detected,
        robot_action_ok=robot_action_ok,
        robot_action_error=robot_action_error,
        transcript=transcript,
    )


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_skill_token)])
async def chat(req: ChatRequest, request: Request):
    return await process_chat_message(
        req.text.strip(), request, speak=bool(req.speak), transcript=None
    )


@app.post("/chat/qr-scan")
async def chat_qr_scan():
    """
    Chụp một frame từ camera robot, decode QR rồi trả kết quả ngắn gọn cho app.
    """
    try:
        raw_img, err = await asyncio.wait_for(_robot_capture_image_bytes(), timeout=10.0)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Robot camera timeout. Kiem tra ket noi robot/IP roi thu lai.")
    if not raw_img:
        raise HTTPException(status_code=503, detail=(err or {}).get("kind") or "robot_camera_unavailable")
    codes = _decode_qr_codes_from_image_bytes(raw_img)
    if not codes:
        return {
            "ok": False,
            "count": 0,
            "codes": [],
            "reply": "Chua thay ma QR. Hay canh lai camera robot va thu lai.",
        }
    first_text = (codes[0].get("text") or "").strip()
    return {
        "ok": True,
        "count": len(codes),
        "codes": codes,
        "reply": f"Da doc duoc QR: {first_text[:160]}",
    }


@app.post("/voice/chat", response_model=ChatResponse)
async def voice_chat(
    request: Request,
    audio: UploadFile = File(..., description="wav | webm | mp3 | ogg | flac"),
    speak: bool = Form(default=True, description="Robot TTS reply (requires ROBOT_SPEAK_REPLIES)"),
):
    """
    STT (Gemini multimodal) → cùng luồng xử lý như POST /chat.
    multipart: file field `audio`, optional form field `speak` = true|false.
    """
    transcript, mime = await transcribe_audio_upload(audio)
    log.info("🎤 STT (%s): %s", mime, transcript[:500].replace("\n", " "))
    return await process_chat_message(
        transcript.strip(), request, speak=bool(speak), transcript=transcript
    )

@app.delete("/chat/history")
async def clear_history():
    global chat_session
    chat_session = client.chats.create(
        model=config.GEMINI_MODEL,
        config=types.GenerateContentConfig(
            system_instruction=config.SYSTEM_PROMPT
        )
    )
    log.info("🗑️ Đã xóa lịch sử chat")
    return {"message": "Đã reset lịch sử hội thoại"}

if __name__ == "__main__":
    import uvicorn
    from uvicorn import Config, Server

    # reload=True tren Windows de gay 2 process / xung dot cong; chi bat khi dat ALPHAMINI_DEV_RELOAD=1
    _reload = os.getenv("ALPHAMINI_DEV_RELOAD", "").strip().lower() in {"1", "true", "yes", "on"}
    _ssl = config.server_ssl_cert_key()
    _common: dict = {
        "host": config.SERVER_HOST,
        "port": config.SERVER_PORT,
        "log_level": "info",
    }
    if _ssl:
        _common["ssl_certfile"], _common["ssl_keyfile"] = _ssl

    if _reload:
        uvicorn.run("server:app", reload=True, **_common)
    else:
        # Bind socket TRUOC lifespan (connect robot). workers=1 + uvicorn.run() bind SAU lifespan -> de loi 10048.
        uvconfig = Config("server:app", **_common)
        uvconfig.load()
        sock = uvconfig.bind_socket()
        Server(config=uvconfig).run(sockets=[sock])
