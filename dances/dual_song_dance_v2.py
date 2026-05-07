# pyright: reportMissingImports=false
"""
Một bài «Ộ I I» — PlayAction + timeline (tempo ~80 BPM).

- PlayAction     → action ngắn (interrupt-safe, tên theo tài liệu/firmware).
- StartBehavior  → có thể gọi thủ công qua DANCE_BEHAVIORS (nhạc riêng firmware).

Chạy: python dual_song_dance_v2.py
.env: ROBOT_IP, ROBOT_TYPE, O_I_I_MP3_URL (hoặc URL_O_I_I / DUAL_URL_O_I_I / ALO_VU_MP3_URL)

Nếu nhạc hết mà robot vẫn nhảy: SDK không báo khi phát xong — đặt DUAL_V2_SONG_DURATION_SEC
bằng độ dài thực của file MP3 (giây) để cắt timeline + StopAllAction lúc đó.

SDK: PlayAction(is_serial, action_name), MoveRobot(is_serial, direction, step),
     StartBehavior(is_serial, name), PlayAudio(is_serial, url, storage_type, volume).
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _ensure_utf8_stdio() -> None:
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                try:
                    stream.reconfigure(encoding="utf-8", errors="replace")
                except Exception:
                    pass


import ws_mini_compat

ws_mini_compat.apply_mini_websocket_compat()

import mini.mini_sdk as MiniSdk
from mini import MoveRobotDirection
from mini.apis.api_action import MoveRobot, PlayAction, StopAllAction
from mini.apis.api_behavior import StartBehavior
from mini.apis.api_expression import MouthLampColor, MouthLampMode, PlayExpression, SetMouthLamp
from mini.apis.api_setup import StartRunProgram
from mini.apis.api_sound import AudioStorageType, PlayAudio, StartPlayTTS, StopAllAudio
from mini.dns.dns_browser import WiFiDevice

logging.basicConfig(level=logging.WARNING)

SERIAL = (os.getenv("ALPHA_SERIAL") or "00018").strip()
ROBOT_IP = (os.getenv("ROBOT_IP") or "").strip()


def _url_song1() -> str:
    return (
        os.getenv("DUAL_URL_O_I_I")
        or os.getenv("URL_O_I_I")
        or os.getenv("O_I_I_MP3_URL")
        or os.getenv("ALO_VU_MP3_URL")
        or ""
    ).strip()


def _set_robot_type_from_env() -> None:
    t = (os.getenv("ROBOT_TYPE") or "mini").strip().lower()
    if t in ("mini", "min"):
        MiniSdk.set_robot_type(MiniSdk.RobotType.MINI)
    elif t == "edu":
        MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)
    elif t in ("dedu", "cn", "china"):
        MiniSdk.set_robot_type(MiniSdk.RobotType.DEDU)
    elif t in ("kor", "kr"):
        MiniSdk.set_robot_type(MiniSdk.RobotType.KOR)
    else:
        MiniSdk.set_robot_type(MiniSdk.RobotType.MINI)


# --- Tempo (~80 BPM) ---
BEAT = float(os.getenv("DUAL_V2_BEAT", "0.75"))
HALF = BEAT / 2
TWO = BEAT * 2
FOUR = BEAT * 4
STAB = float(os.getenv("DUAL_V2_STAB", "0.55"))


def _song_duration_cap_sec() -> float | None:
    """Giới hạn thời gian nhảy = độ dài nhạc (giây). None = chạy hết timeline (~155s)."""
    v = (os.getenv("DUAL_V2_SONG_DURATION_SEC") or "").strip()
    if not v:
        return None
    try:
        x = float(v.replace(",", "."))
        return x if x >= 3.0 else None
    except ValueError:
        return None


# --- Action ngắn (PlayAction) — tên phụ thuộc firmware; lỗi thì bỏ qua ---
LIGHT_ACTIONS = [
    "random_short3",
    "random_short4",
    "011",
    "017",
    "037",
    "015",
    "010",
    "038",
    "Surveillance_004",
    "Surveillance_006",
    "action_005",
    "action_006",
    "action_018",
    "action_015",
    "action_004",
]

# --- Dance dài (StartBehavior) — có nhạc riêng trên robot; gọi tùy chọn ---
DANCE_BEHAVIORS = [
    "dance_0006en",
    "dance_0005en",
    "dance_0001en",
    "dance_0009en",
    "dance_0003en",
]

_running = True
_current_pattern = "groove_wave"


async def _act(name: str) -> None:
    if not name:
        await asyncio.sleep(BEAT)
        return
    try:
        await PlayAction(is_serial=True, action_name=name).execute()
        await asyncio.sleep(0.12)
    except Exception:
        await asyncio.sleep(0.2)


async def _behavior(name: str) -> None:
    try:
        await StartBehavior(is_serial=True, name=name).execute()
    except Exception:
        pass


async def _go(direction: int) -> None:
    """1=tiến 2=lùi 3=trái 4=phải (khớp dual_song_dance.py)."""
    dmap = {
        1: MoveRobotDirection.FORWARD,
        2: MoveRobotDirection.BACKWARD,
        3: MoveRobotDirection.LEFTWARD,
        4: MoveRobotDirection.RIGHTWARD,
    }
    d = dmap.get(direction, MoveRobotDirection.FORWARD)
    try:
        await MoveRobot(is_serial=False, direction=d, step=1).execute()
    except Exception:
        pass
    await asyncio.sleep(STAB)


def _lamp_breath(speed: str = "mid", color: str = "green") -> None:
    """SDK chỉ có RED/GREEN/WHITE — không có RGB tuỳ ý."""
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


async def _face(name: str) -> None:
    try:
        await PlayExpression(is_serial=False, express_name=name).execute()
    except Exception:
        pass


def _say(text: str) -> None:
    asyncio.create_task(StartPlayTTS(is_serial=False, text=text).execute())


def set_pattern(name: str) -> None:
    global _current_pattern
    if name in PATTERNS:
        _current_pattern = name


async def pattern_groove_wave() -> None:
    await _go(3)
    await asyncio.sleep(HALF)
    await _act("random_short3")
    await asyncio.sleep(HALF)
    await _go(4)
    await asyncio.sleep(HALF)
    await _act("random_short4")
    await asyncio.sleep(HALF)


async def pattern_nod_sway() -> None:
    await _act("011")
    await asyncio.sleep(HALF)
    await _go(3)
    await asyncio.sleep(HALF)
    await _act("037")
    await asyncio.sleep(HALF)
    await _go(4)
    await asyncio.sleep(HALF)


async def pattern_raise_sway() -> None:
    await _act("017")
    await asyncio.sleep(TWO)
    await _go(3)
    await asyncio.sleep(HALF)
    await _go(4)
    await asyncio.sleep(HALF)


async def pattern_cute_groove() -> None:
    await _act("Surveillance_006")
    await asyncio.sleep(BEAT)
    await _go(1)
    await asyncio.sleep(HALF)
    await _act("action_005")
    await asyncio.sleep(BEAT)
    await _go(2)
    await asyncio.sleep(HALF)


async def pattern_hey_ha() -> None:
    await _act("action_018")
    await asyncio.sleep(BEAT)
    await _go(3)
    await asyncio.sleep(HALF)
    await _go(4)
    await asyncio.sleep(HALF)
    await _act("action_004")
    await asyncio.sleep(HALF)


async def pattern_ok_wave() -> None:
    await _act("action_006")
    await asyncio.sleep(BEAT)
    await _act("random_short4")
    await asyncio.sleep(HALF)
    await _go(3)
    await asyncio.sleep(HALF)
    await _act("random_short3")
    await asyncio.sleep(HALF)
    await _go(4)
    await asyncio.sleep(HALF)


async def pattern_tilt_step() -> None:
    await _act("038")
    await asyncio.sleep(HALF)
    await _go(3)
    await asyncio.sleep(HALF)
    await _act("038")
    await asyncio.sleep(HALF)
    await _go(4)
    await asyncio.sleep(HALF)


async def pattern_sway_only() -> None:
    await _go(3)
    await asyncio.sleep(BEAT)
    await _go(4)
    await asyncio.sleep(BEAT)
    await _go(3)
    await asyncio.sleep(BEAT)
    await _go(4)
    await asyncio.sleep(BEAT)


PATTERNS = {
    "groove_wave": pattern_groove_wave,
    "nod_sway": pattern_nod_sway,
    "raise_sway": pattern_raise_sway,
    "cute_groove": pattern_cute_groove,
    "hey_ha": pattern_hey_ha,
    "ok_wave": pattern_ok_wave,
    "tilt_step": pattern_tilt_step,
    "sway_only": pattern_sway_only,
}


async def dance_loop() -> None:
    global _running
    while _running:
        fn = PATTERNS.get(_current_pattern, pattern_groove_wave)
        await fn()


async def sleep_until(
    target_sec: float,
    t0: float,
    max_elapsed: float | None = None,
) -> bool:
    """Đợi đến mốc target_sec giây kể từ t0. Trả về True = cần dừng hẳn timeline (đã tới giới hạn nhạc)."""
    now = time.monotonic()
    if max_elapsed is not None:
        limit = t0 + max_elapsed
        if now >= limit:
            return True
    rem = target_sec - (now - t0)
    if max_elapsed is not None:
        limit = t0 + max_elapsed
        cap_rem = limit - now
        if cap_rem <= 0.05:
            return True
        rem = min(rem, cap_rem)
    if rem > 0.1:
        await asyncio.sleep(rem)
    if max_elapsed is not None and time.monotonic() >= t0 + max_elapsed:
        return True
    return False


async def _stop_moves_for_timeline_cap() -> None:
    """Nhạc đã hết (theo cap) — dừng vòng nhảy và cắt action đang chạy."""
    global _running
    _running = False
    try:
        await StopAllAction(is_serial=False).execute()
    except Exception:
        pass


async def timeline_o_i_i(t0: float) -> None:
    max_e = _song_duration_cap_sec()

    set_pattern("groove_wave")
    _lamp_breath("slow", "green")
    await _face("codemao10")

    if await sleep_until(10, t0, max_e):
        await _stop_moves_for_timeline_cap()
        return
    set_pattern("nod_sway")
    _lamp_breath("mid", "green")

    if await sleep_until(25, t0, max_e):
        await _stop_moves_for_timeline_cap()
        return
    set_pattern("cute_groove")
    _lamp_breath("mid", "green")

    if await sleep_until(35, t0, max_e):
        await _stop_moves_for_timeline_cap()
        return
    set_pattern("hey_ha")
    _lamp_breath("fast", "green")
    await _face("codemao10")
    _say("Ô i i!")

    if await sleep_until(45, t0, max_e):
        await _stop_moves_for_timeline_cap()
        return
    set_pattern("raise_sway")
    _lamp_breath("fast", "green")

    if await sleep_until(55, t0, max_e):
        await _stop_moves_for_timeline_cap()
        return
    set_pattern("ok_wave")
    _lamp_breath("mid", "green")

    if await sleep_until(70, t0, max_e):
        await _stop_moves_for_timeline_cap()
        return
    set_pattern("tilt_step")
    _lamp_breath("mid", "green")

    if await sleep_until(80, t0, max_e):
        await _stop_moves_for_timeline_cap()
        return
    set_pattern("hey_ha")
    _lamp_breath("fast", "green")
    _say("Ộ i i! Alo Vũ!")

    if await sleep_until(95, t0, max_e):
        await _stop_moves_for_timeline_cap()
        return
    set_pattern("sway_only")
    _lamp_breath("slow", "green")

    if await sleep_until(110, t0, max_e):
        await _stop_moves_for_timeline_cap()
        return
    set_pattern("raise_sway")
    _lamp_breath("fast", "green")
    _say("Ộ i i! Alo Vũ Mixi!")

    if await sleep_until(140, t0, max_e):
        await _stop_moves_for_timeline_cap()
        return
    set_pattern("groove_wave")
    _lamp_breath("slow", "green")
    await _face("emo_007")

    if await sleep_until(155, t0, max_e):
        await _stop_moves_for_timeline_cap()


async def _run_song1(t0: float) -> None:
    global _running
    await timeline_o_i_i(t0)
    _running = False


async def _play_track(url: str) -> None:
    if not url.startswith("http"):
        print(f"⚠️  URL không hợp lệ: {url[:48]}...")
        return
    ok = await MiniSdk.play_online_audio(url)
    if not ok:
        print("⚠️  play_online_audio trả về False — thử PlayAudio SDK…")
        try:
            await PlayAudio(
                is_serial=False,
                url=url,
                storage_type=AudioStorageType.NET_PUBLIC,
                volume=1.0,
            ).execute()
        except Exception as e:
            print(f"⚠️  PlayAudio: {e}")


def stop_dual_song_dance_v2() -> None:
    global _running
    _running = False


async def perform_o_i_i() -> None:
    global _running

    u1 = _url_song1()

    cap = _song_duration_cap_sec()
    print("\n🎵 Ộ I I...")
    if cap:
        print(f"   Đồng bộ nhảy ~{cap:.1f}s (DUAL_V2_SONG_DURATION_SEC)")
    else:
        print(
            "   Nếu nhạc hết mà vẫn nhảy: đặt DUAL_V2_SONG_DURATION_SEC = độ dài MP3 (giây)."
        )
    if u1:
        asyncio.create_task(_play_track(u1))
    else:
        print("⚠️  Thiếu URL (O_I_I_MP3_URL / URL_O_I_I / DUAL_URL_O_I_I).")

    t1 = time.monotonic()
    _running = True
    set_pattern("groove_wave")
    await asyncio.gather(dance_loop(), _run_song1(t1))

    print("\n✅ Xong!")


async def main() -> None:
    _ensure_utf8_stdio()
    MiniSdk.set_log_level(logging.WARNING)
    _set_robot_type_from_env()

    print(f"🔌 Kết nối (serial={SERIAL!r}, ROBOT_IP={'có' if ROBOT_IP else 'mDNS'})...")
    if ROBOT_IP:
        device: WiFiDevice | None = WiFiDevice(name="AlphaMini", address=ROBOT_IP)
        print(f"   → IP {ROBOT_IP}")
    else:
        device = await MiniSdk.get_device_by_name(SERIAL, timeout=20)

    if not device:
        print("❌ Không tìm thấy robot. Đặt ROBOT_IP trong .env.")
        return

    if not await MiniSdk.connect(device):
        print("❌ Kết nối thất bại.")
        return

    try:
        await StartRunProgram().execute()
    except Exception:
        try:
            await MiniSdk.enter_program()
        except Exception:
            pass
    await asyncio.sleep(2.0)
    print("✅ Robot sẵn sàng.")

    try:
        await perform_o_i_i()
    except asyncio.CancelledError:
        stop_dual_song_dance_v2()
        raise
    except Exception as e:
        print(f"❌ Lỗi: {e}")
    finally:
        stop_dual_song_dance_v2()
        try:
            await StopAllAction(is_serial=False).execute()
        except Exception:
            pass
        try:
            await StopAllAudio(is_serial=False).execute()
        except Exception:
            pass
        try:
            await MiniSdk.stop_audio()
        except Exception:
            pass
        await asyncio.sleep(0.3)
        await MiniSdk.release()
        print("🔌 Đã ngắt kết nối.")


if __name__ == "__main__":
    asyncio.run(main())
