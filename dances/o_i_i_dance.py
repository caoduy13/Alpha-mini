# pyright: reportMissingImports=false
"""
Robot Alpha Mini — nhảy theo bài "Ộ I I" / Alo Vũ ( vibe Độ Mixi ).
Điệu: lắc vai + nhún theo beat ~115 BPM (BEAT ≈ 0.52s).

Chạy: python o_i_i_dance.py
Biến môi trường: ROBOT_IP, O_I_I_MP3_URL, …
  O_I_I_NA_NA_BACKING=1 → giữ vũ đạo/timeline "Ộ I I" nhưng phát nhạc nền "nà ná na na"
    (AN_DO_MIXI_MP3_URL / QUY_KHOI_MP3_URL / link Drive mặc định).
  O_I_I_RUN_SEC=15 → tự dừng nhảy + timeline sau 15 giây (thử nhanh / demo).
  Nhạc không ra: Google Drive thường không tải được trên robot → bật server + đặt MP3
    trong robot_music/ và ROBOT_AUDIO_PUBLIC_URL + O_I_I_LAN_MP3=tên_file.mp3
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import time

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
except ImportError:
    pass


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


import mini.mini_sdk as MiniSdk
from mini import MoveRobotDirection
from mini.apis.api_action import MoveRobot, PlayAction, StopAllAction
from mini.apis.api_expression import MouthLampColor, MouthLampMode, PlayExpression, SetMouthLamp
from mini.apis.api_sound import StartPlayTTS
from mini.dns.dns_browser import WiFiDevice

logging.basicConfig(level=logging.WARNING)

# ==================== CONFIG ====================
SERIAL = (os.getenv("ALPHA_SERIAL") or "00018").strip()
ROBOT_IP = (os.getenv("ROBOT_IP") or "").strip()

_NA_NA_DRIVE_ID = "1sC1aNXJALEiUFyyhoW3J-j3lyDS5JyLX"


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _na_na_url() -> str:
    return (
        os.getenv("AN_DO_MIXI_MP3_URL")
        or os.getenv("QUY_KHOI_MP3_URL")
        or f"https://drive.google.com/uc?export=download&id={_NA_NA_DRIVE_ID}"
    ).strip()


def _default_music_url() -> str:
    """
    Mặc định: URL bài Ộ I I.
    O_I_I_NA_NA_BACKING=1: nhạc nền nà ná na na, vẫn dùng timeline o_i_i.
    """
    if _env_bool("O_I_I_NA_NA_BACKING", default=False):
        u = _na_na_url()
        if u:
            return u
    return (
        os.getenv("O_I_I_MP3_URL")
        or os.getenv("ALO_VU_MP3_URL")
        or os.getenv("AN_DO_MIXI_MP3_URL")
        or ""
    ).strip()


MUSIC_URL = _default_music_url()


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        u = (u or "").strip()
        if u.startswith("http") and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _drive_extra_urls(url: str) -> list[str]:
    """Robot hay lỗi với drive.google.com/uc — thêm biến thể."""
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if not m:
        return []
    fid = m.group(1)
    return [
        f"https://drive.usercontent.google.com/uc?export=download&id={fid}",
        f"https://drive.google.com/uc?export=download&id={fid}&confirm=t",
    ]


def _lan_music_url() -> str:
    """MP3 phục vụ bởi Alpha Mini Server — robot tải qua LAN (ổn định nhất)."""
    base = (os.getenv("ROBOT_AUDIO_PUBLIC_URL") or "").strip().rstrip("/")
    name = (os.getenv("O_I_I_LAN_MP3") or "").strip()
    if base and name:
        return f"{base}/robot/music/{name}"
    return ""


def _http_play_url_override() -> str:
    """URL MP3 đầy đủ (vd. http://IP:8088/na_na_mixi.mp3) — ưu tiên cao nhất."""
    return (
        os.getenv("O_I_I_HTTP_PLAY_URL")
        or os.getenv("O_I_I_LAN_FULL_URL")
        or ""
    ).strip()


def music_play_candidates(primary: str) -> list[str]:
    """Thứ tự: URL tuyệt đối .env → LAN FastAPI /robot/music/ → URL chính → Drive mirror."""
    cand: list[str] = []
    override = _http_play_url_override()
    if override.startswith("http"):
        cand.append(override)
    lan = _lan_music_url()
    if lan:
        cand.append(lan)
    p = (primary or "").strip()
    if p.startswith("http"):
        cand.append(p)
        if "drive.google.com" in p.lower() or "docs.google.com" in p.lower():
            cand.extend(_drive_extra_urls(p))
    return _dedupe_urls(cand)


# Tempo 115 BPM → 60/115 s
BEAT = float(os.getenv("O_I_I_BEAT", str(60 / 115)))
HALF = BEAT / 2
TWO = BEAT * 2
FOUR = BEAT * 4

# Ưu tiên mã inner cho vai / tay (sau discover có thể ghi đè)
PREF_WAVE = "018"
PREF_RAISE = "017"
PREF_DANCE = "020"

WAVE_ACTION: str | None = None
RAISE_ACTION: str | None = None
DANCE1_ACTION: str | None = None
WORKING_ACTIONS: list[str] = []

_running = True
_current_pattern = "shoulder_groove"


def stop_o_i_i_dance() -> None:
    global _running
    _running = False


def _set_robot_type_from_env() -> None:
    t = (os.getenv("ROBOT_TYPE") or "edu").strip().lower()
    if t in ("mini", "min"):
        MiniSdk.set_robot_type(MiniSdk.RobotType.MINI)
    elif t == "edu":
        MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)
    elif t in ("dedu", "cn", "china"):
        MiniSdk.set_robot_type(MiniSdk.RobotType.DEDU)
    elif t in ("kor", "kr"):
        MiniSdk.set_robot_type(MiniSdk.RobotType.KOR)
    else:
        MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)


# ==================== DISCOVERY ====================


def apply_preset_actions() -> None:
    """Không quét — dùng mã inner phổ biến (đã biết OK trên máy bạn)."""
    global WAVE_ACTION, RAISE_ACTION, DANCE1_ACTION, WORKING_ACTIONS
    w = (os.getenv("O_I_I_WAVE") or PREF_WAVE).strip()
    r = (os.getenv("O_I_I_RAISE") or PREF_RAISE).strip()
    d = (os.getenv("O_I_I_DANCE") or PREF_DANCE or "016").strip()
    WORKING_ACTIONS = [x for x in (w, r, d) if x]
    WAVE_ACTION, RAISE_ACTION, DANCE1_ACTION = w, r, d
    print("⚡ Bỏ quét action — preset (đổi bằng O_I_I_WAVE / O_I_I_RAISE / O_I_I_DANCE nếu cần)")
    print(f"🎯 WAVE={WAVE_ACTION} | RAISE={RAISE_ACTION} | DANCE1={DANCE1_ACTION}")


async def discover_actions() -> None:
    """Quét action inner phổ biến; gán wave / raise / dance theo mã ưu tiên."""
    global WAVE_ACTION, RAISE_ACTION, DANCE1_ACTION, WORKING_ACTIONS

    # Quét nhanh: chờ ngắn sau mỗi lệnh OK (trước đây 1.2s làm mất ~1 phút)
    pause_ok = float(os.getenv("O_I_I_DISCOVER_PAUSE_OK", "0.35"))
    pause_fail = float(os.getenv("O_I_I_DISCOVER_PAUSE_FAIL", "0.12"))

    candidates = [
        "018",
        "017",
        "016",
        "015",
        "014",
        "013",
        "012",
        *[f"{i:03d}" for i in range(1, 12)],
        *[f"{i:03d}" for i in range(19, 29)],
        "dance_0001en",
        "dance_0002en",
        "dance_0003en",
    ]

    WORKING_ACTIONS = []
    print("🔍 Đang tìm action hoạt động (quét đầy đủ)...")
    for name in candidates:
        try:
            _, resp = await PlayAction(action_name=name, is_serial=True).execute()
            if resp and getattr(resp, "isSuccess", False):
                WORKING_ACTIONS.append(name)
                print(f"  ✅ {name!r}")
                await asyncio.sleep(pause_ok)
            else:
                rc = getattr(resp, "resultCode", "?") if resp else "?"
                print(f"  ❌ {name!r} (rc={rc})")
                await asyncio.sleep(pause_fail)
        except Exception as e:
            print(f"  ⚠️  {name!r}: {e}")
            await asyncio.sleep(pause_fail)

    wset = set(WORKING_ACTIONS)
    WAVE_ACTION = PREF_WAVE if PREF_WAVE in wset else (WORKING_ACTIONS[0] if WORKING_ACTIONS else None)
    RAISE_ACTION = PREF_RAISE if PREF_RAISE in wset else None
    DANCE1_ACTION = PREF_DANCE if PREF_DANCE in wset else None
    if RAISE_ACTION is None:
        for x in WORKING_ACTIONS:
            if x != WAVE_ACTION:
                RAISE_ACTION = x
                break
    if DANCE1_ACTION is None:
        for x in WORKING_ACTIONS:
            if x not in (WAVE_ACTION, RAISE_ACTION):
                DANCE1_ACTION = x
                break

    print(f"\n✅ WORKING ({len(WORKING_ACTIONS)}): {WORKING_ACTIONS}")
    print(f"🎯 WAVE={WAVE_ACTION} | RAISE={RAISE_ACTION} | DANCE1={DANCE1_ACTION}")


# ==================== LAMP / FACE (SDK enum) ====================


def _lamp_breath(speed: str = "mid", color: str = "green") -> None:
    """Đèn miệng — không chặn timeline."""
    c = MouthLampColor.GREEN if color == "green" else MouthLampColor.RED
    dur_map = {"slow": 1880, "mid": 800, "fast": 400}
    asyncio.create_task(
        SetMouthLamp(
            is_serial=False,
            color=c,
            mode=MouthLampMode.BREATH,
            duration=6000,
            breath_duration=dur_map.get(speed, 800),
        ).execute()
    )


def _face(name: str) -> None:
    # codemao1 = vui; 2 = tập trung; 3 = excited
    asyncio.create_task(PlayExpression(is_serial=False, express_name=name).execute())


def _say(text: str) -> None:
    asyncio.create_task(StartPlayTTS(is_serial=False, text=text).execute())


# ==================== PRIMITIVES ====================


async def _safe_action(name: str | None, post_wait: float = 0.15) -> None:
    """PlayAction trong nhảy: is_serial=False; lỗi thì chờ nhịp ngắn."""
    if not name:
        await asyncio.sleep(min(BEAT * 0.5, 0.35))
        return
    try:
        _, resp = await PlayAction(action_name=name, is_serial=False).execute()
        if resp and getattr(resp, "isSuccess", False):
            await asyncio.sleep(min(post_wait, 0.25))
        else:
            await asyncio.sleep(0.15)
    except Exception:
        await asyncio.sleep(0.2)


async def _step_left() -> None:
    try:
        await MoveRobot(
            is_serial=False, direction=MoveRobotDirection.LEFTWARD, step=1
        ).execute()
    except Exception:
        pass
    await asyncio.sleep(0.35)


async def _step_right() -> None:
    try:
        await MoveRobot(
            is_serial=False, direction=MoveRobotDirection.RIGHTWARD, step=1
        ).execute()
    except Exception:
        pass
    await asyncio.sleep(0.35)


async def _step_forward() -> None:
    try:
        await MoveRobot(
            is_serial=False, direction=MoveRobotDirection.FORWARD, step=1
        ).execute()
    except Exception:
        pass
    await asyncio.sleep(0.35)


async def _step_back() -> None:
    try:
        await MoveRobot(
            is_serial=False, direction=MoveRobotDirection.BACKWARD, step=1
        ).execute()
    except Exception:
        pass
    await asyncio.sleep(0.35)


# ==================== PATTERNS (1 bar ≈ 4 beat) ====================


async def pattern_shoulder_groove() -> None:
    await _step_left()
    await asyncio.sleep(HALF)
    await _safe_action(WAVE_ACTION)
    await asyncio.sleep(HALF)
    await _step_right()
    await asyncio.sleep(HALF)
    await _safe_action(WAVE_ACTION)
    await asyncio.sleep(HALF)


async def pattern_wave_heavy() -> None:
    await _safe_action(WAVE_ACTION)
    await asyncio.sleep(BEAT)
    await _safe_action(WAVE_ACTION)
    await asyncio.sleep(BEAT)
    await _safe_action(WAVE_ACTION)
    await asyncio.sleep(BEAT)
    await _safe_action(WAVE_ACTION)
    await asyncio.sleep(BEAT)


async def pattern_raise_sway() -> None:
    act = RAISE_ACTION or WAVE_ACTION
    await _safe_action(act, post_wait=0.2)
    await asyncio.sleep(min(TWO, BEAT * 3.5))
    await _step_left()
    await asyncio.sleep(HALF)
    await _step_right()
    await asyncio.sleep(HALF)


async def pattern_forward_back() -> None:
    await _step_forward()
    await asyncio.sleep(HALF)
    await _safe_action(WAVE_ACTION)
    await asyncio.sleep(HALF)
    await _step_back()
    await asyncio.sleep(HALF)
    await _safe_action(WAVE_ACTION)
    await asyncio.sleep(HALF)


async def pattern_hype() -> None:
    action = DANCE1_ACTION or RAISE_ACTION or WAVE_ACTION
    await _safe_action(action)
    await asyncio.sleep(BEAT)
    await _step_left()
    await _step_right()
    await asyncio.sleep(BEAT)


async def pattern_chill() -> None:
    await _step_left()
    await asyncio.sleep(BEAT)
    await _step_right()
    await asyncio.sleep(BEAT)
    await _step_left()
    await asyncio.sleep(BEAT)
    await _step_right()
    await asyncio.sleep(BEAT)


PATTERNS: dict[str, object] = {
    "shoulder_groove": pattern_shoulder_groove,
    "wave_heavy": pattern_wave_heavy,
    "raise_sway": pattern_raise_sway,
    "forward_back": pattern_forward_back,
    "hype": pattern_hype,
    "chill": pattern_chill,
}


def set_pattern(name: str) -> None:
    global _current_pattern
    if name in PATTERNS:
        _current_pattern = name


# ================= ENGINE ====================


async def dance_loop() -> None:
    global _running
    bar = 0
    while _running:
        pattern_fn = PATTERNS.get(_current_pattern, pattern_shoulder_groove)
        await pattern_fn()  # type: ignore[misc]
        bar += 1
        if bar % 16 == 0 and _current_pattern == "shoulder_groove":
            set_pattern("forward_back")
        elif bar % 16 == 8 and _current_pattern == "forward_back":
            set_pattern("shoulder_groove")


async def sleep_until(target_sec: float, t0: float) -> None:
    rem = target_sec - (time.time() - t0)
    if rem > 0.05:
        await asyncio.sleep(rem)


async def music_timeline(t0: float) -> None:
    global _running

    set_pattern("shoulder_groove")
    _lamp_breath("slow", "green")
    _face("codemao1")

    await sleep_until(8.0, t0)
    set_pattern("shoulder_groove")
    _lamp_breath("mid", "green")

    await sleep_until(20.0, t0)
    set_pattern("forward_back")
    _lamp_breath("mid", "green")

    await sleep_until(30.0, t0)
    set_pattern("wave_heavy")
    _lamp_breath("fast", "green")
    _face("codemao1")
    _say("Ô i i!")

    await sleep_until(38.0, t0)
    set_pattern("raise_sway")
    _lamp_breath("fast", "red")

    await sleep_until(50.0, t0)
    set_pattern("shoulder_groove")
    _lamp_breath("slow", "green")

    await sleep_until(65.0, t0)
    set_pattern("forward_back")
    _lamp_breath("mid", "green")

    await sleep_until(75.0, t0)
    set_pattern("hype")
    _lamp_breath("fast", "red")
    _face("codemao3")
    _say("Ộ i i! Alo Vũ!")

    await sleep_until(85.0, t0)
    set_pattern("wave_heavy")
    _lamp_breath("fast", "green")

    await sleep_until(95.0, t0)
    set_pattern("raise_sway")
    _lamp_breath("mid", "green")

    await sleep_until(100.0, t0)
    set_pattern("chill")
    _lamp_breath("slow", "green")

    await sleep_until(115.0, t0)
    set_pattern("hype")
    _lamp_breath("fast", "red")
    _say("Ộ i i! Alo Vũ Mixi!")

    await sleep_until(130.0, t0)
    set_pattern("wave_heavy")
    _lamp_breath("fast", "green")

    await sleep_until(140.0, t0)
    set_pattern("shoulder_groove")
    _lamp_breath("slow", "green")
    _face("codemao1")
    _say("Xin chào mọi người!")

    await asyncio.sleep(10)
    _running = False
    print("✅ Timeline kết thúc.")


async def _play_music_bg(primary_url: str) -> None:
    """Thử nhiều URL; tăng âm lượng; fallback PlayAudio (một số firmware)."""
    from mini import mini_sdk

    urls = music_play_candidates(primary_url)
    if not urls:
        print("⚠️  Không có URL nhạc hợp lệ.")
        return

    try:
        await mini_sdk.stop_audio()
    except Exception:
        pass
    try:
        await mini_sdk.stop_tts()
    except Exception:
        pass
    try:
        vol = float(os.getenv("O_I_I_VOLUME", "0.95"))
        await mini_sdk.change_volume(max(0.0, min(1.0, vol)))
    except Exception:
        pass
    await asyncio.sleep(0.2)

    for u in urls:
        try:
            ok = await mini_sdk.play_online_audio(u)
            print(f"🔊 play_online_audio → {'OK' if ok else 'FALSE'} | {u[:88]}…")
            if ok:
                return
        except Exception as e:
            print(f"⚠️  play_online_audio lỗi: {e} | {u[:72]}…")

    try:
        from mini.apis.api_sound import AudioStorageType, PlayAudio

        u0 = urls[0]
        await PlayAudio(url=u0, storage_type=AudioStorageType.NET_PUBLIC).execute()
        print("🔊 PlayAudio(NET_PUBLIC) đã gọi (kiểm tra loa robot).")
    except Exception as e:
        print(f"⚠️  PlayAudio fallback: {e}")

    print(
        "❌ Không phát được nhạc. Gợi ý: (1) Chạy server + copy MP3 vào robot_music/ "
        "và đặt O_I_I_LAN_MP3 + ROBOT_AUDIO_PUBLIC_URL=IP máy tính "
        "(2) Dùng link MP3 trực tiếp không qua trang xác nhận Drive."
    )


async def run_o_i_i_show(mp3_url: str | None = None) -> None:
    """Gọi khi đã MiniSdk.connect (vd. từ server)."""
    global MUSIC_URL, _running
    # Gọi từ server không qua `main()` → chưa discover/preset: WAVE_ACTION rỗng → gần như không nhảy.
    if not WORKING_ACTIONS or WAVE_ACTION is None:
        _set_robot_type_from_env()
        skip = _env_bool("O_I_I_SKIP_DISCOVER", default=bool((os.getenv("ROBOT_IP") or "").strip()))
        if skip:
            apply_preset_actions()
        else:
            await discover_actions()
    MUSIC_URL = (mp3_url or _default_music_url() or MUSIC_URL).strip()
    _running = True
    set_pattern("shoulder_groove")
    print("🎵 Ộ I I — Alo Vũ (vũ đạo)")
    if _env_bool("O_I_I_NA_NA_BACKING", default=False):
        print("   🎶 Nhạc nền: Nà ná na na (Ấn Độ Mixi)")
    print("=" * 50)
    override = _http_play_url_override()
    if MUSIC_URL.startswith("http") or _lan_music_url() or override.startswith("http"):
        if MUSIC_URL.startswith("http"):
            prim = MUSIC_URL
        elif override.startswith("http"):
            prim = override
        else:
            prim = _lan_music_url()
        asyncio.create_task(_play_music_bg(prim))
        delay = float(os.getenv("O_I_I_MUSIC_START_DELAY", "1.0"))
        await asyncio.sleep(delay)
    else:
        print("⚠️  Chưa có URL nhạc — chỉ nhảy. Thêm O_I_I_MP3_URL hoặc O_I_I_HTTP_PLAY_URL (xem docstring).")
    t0 = time.time()
    try:
        max_run = float((os.getenv("O_I_I_RUN_SEC") or "0").strip() or "0")
    except ValueError:
        max_run = 0.0
    if max_run > 0:
        print(f"⏱️  Tự dừng sau {max_run:g}s — O_I_I_RUN_SEC")
        try:
            await asyncio.wait_for(
                asyncio.gather(dance_loop(), music_timeline(t0)),
                timeout=max_run,
            )
        except asyncio.TimeoutError:
            stop_o_i_i_dance()
            print(f"⏱️  Đã dừng sau {max_run:g}s.")
            try:
                from mini import mini_sdk

                await mini_sdk.stop_audio()
            except Exception:
                pass
    else:
        await asyncio.gather(dance_loop(), music_timeline(t0))
    print("=" * 50)
    print("✅ Hoàn thành!")


async def main() -> None:
    _ensure_utf8_stdio()
    MiniSdk.set_log_level(logging.WARNING)
    _set_robot_type_from_env()

    print(f"🔌 Kết nối robot (serial={SERIAL!r} | ROBOT_IP={'có' if ROBOT_IP else 'không'})...")
    # Có ROBOT_IP → kết nối thẳng, không chờ quét mDNS/Bonjour serial (~20s)
    device: WiFiDevice | None
    if ROBOT_IP:
        device = WiFiDevice(name="AlphaMini", address=ROBOT_IP)
        print(f"   → Kết nối trực tiếp IP {ROBOT_IP}")
    else:
        device = await MiniSdk.get_device_by_name(SERIAL, timeout=20)
        if not device:
            print("❌ Không quét được serial. Đặt ROBOT_IP trong .env để nhảy ngay.")
            return

    if not await MiniSdk.connect(device):
        print("❌ Kết nối thất bại.")
        return

    try:
        await MiniSdk.enter_program()
    except Exception:
        pass
    await asyncio.sleep(1.0)

    # Mặc định: có ROBOT_IP thì bỏ quét, dùng preset → vào nhảy ngay
    skip_discover = _env_bool("O_I_I_SKIP_DISCOVER", default=bool(ROBOT_IP))
    if skip_discover:
        apply_preset_actions()
    else:
        await discover_actions()
    if not WORKING_ACTIONS:
        print("⚠️  Không có action — vẫn thử nhảy (chỉ MoveRobot + safe fail).")

    try:
        await run_o_i_i_show(_default_music_url())
    except asyncio.CancelledError:
        stop_o_i_i_dance()
        raise
    except Exception as e:
        print(f"❌ Lỗi: {e}")
    finally:
        stop_o_i_i_dance()
        try:
            await StopAllAction(is_serial=False).execute()
        except Exception:
            pass
        try:
            from mini import mini_sdk

            await mini_sdk.stop_audio()
        except Exception:
            pass
        await asyncio.sleep(0.5)
        await MiniSdk.release()
        print("🔌 Đã ngắt kết nối.")


if __name__ == "__main__":
    asyncio.run(main())
