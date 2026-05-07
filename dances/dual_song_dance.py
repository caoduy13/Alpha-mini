# pyright: reportMissingImports=false
"""
Nhảy 2 bài liên tiếp — chậm, đều, an toàn (~80 BPM feel):
  Bài 1: "Ộ I I" (Alo Vũ)
  Bài 2: "Ấn Độ Mixi (Nà Ná Na Na)"

Chạy: python dual_song_dance.py
.env: ROBOT_IP, ROBOT_TYPE, O_I_I_MP3_URL, AN_DO_MIXI_MP3_URL (hoặc DUAL_URL_*)
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

SERIAL = (os.getenv("ALPHA_SERIAL") or "00018").strip()
ROBOT_IP = (os.getenv("ROBOT_IP") or "").strip()

_DRIVE_NA = "1sC1aNXJALEiUFyyhoW3J-j3lyDS5JyLX"


def _url_song1() -> str:
    return (
        os.getenv("DUAL_URL_O_I_I")
        or os.getenv("URL_O_I_I")
        or os.getenv("O_I_I_MP3_URL")
        or os.getenv("ALO_VU_MP3_URL")
        or ""
    ).strip()


def _url_song2() -> str:
    u = (
        os.getenv("DUAL_URL_NA_NA")
        or os.getenv("URL_NA_NA_NA")
        or os.getenv("AN_DO_MIXI_MP3_URL")
        or os.getenv("QUY_KHOI_MP3_URL")
        or ""
    ).strip()
    if u:
        return u
    return f"https://drive.google.com/uc?export=download&id={_DRIVE_NA}"


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


# --- Tempo chậm, đều (80 BPM) ---
BEAT = float(os.getenv("DUAL_BEAT", "0.75"))
HALF = float(os.getenv("DUAL_HALF", str(round(BEAT / 2, 2))))
TWO = BEAT * 2
FOUR = BEAT * 4
STAB = float(os.getenv("DUAL_STAB", "0.55"))

WAVE_ACTION: str | None = None
RAISE_ACTION: str | None = None
WORKING_ACTIONS: list[str] = []

_running = True
_current_pattern = "groove"


def stop_dual_song_dance() -> None:
    global _running
    _running = False


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


def apply_preset_actions() -> None:
    global WAVE_ACTION, RAISE_ACTION, WORKING_ACTIONS
    w = (os.getenv("DUAL_WAVE") or "018").strip()
    r = (os.getenv("DUAL_RAISE") or "017").strip()
    WORKING_ACTIONS = [w, r]
    WAVE_ACTION, RAISE_ACTION = w, r
    print("⚡ Preset action — WAVE=%s RAISE=%s" % (WAVE_ACTION, RAISE_ACTION))


async def discover_actions() -> None:
    global WAVE_ACTION, RAISE_ACTION, WORKING_ACTIONS
    candidates = [
        "018",
        "017",
        "016",
        "015",
        "014",
        "013",
        "012",
        "011",
        "010",
        *[f"{i:03d}" for i in range(1, 10)],
        *[f"{i:03d}" for i in range(19, 26)],
        "dance_0001en",
        "dance_0002en",
    ]
    WORKING_ACTIONS = []
    print("🔍 Khám phá action...")
    pause_ok = float(os.getenv("DUAL_DISCOVER_PAUSE_OK", "0.35"))
    pause_fail = float(os.getenv("DUAL_DISCOVER_PAUSE_FAIL", "0.12"))
    for name in candidates:
        try:
            _, resp = await PlayAction(action_name=name, is_serial=True).execute()
            if resp and getattr(resp, "isSuccess", False):
                WORKING_ACTIONS.append(name)
                print(f"  ✅ {name!r}")
                await asyncio.sleep(pause_ok)
            else:
                await asyncio.sleep(pause_fail)
        except Exception:
            await asyncio.sleep(pause_fail)
    if WORKING_ACTIONS:
        WAVE_ACTION = WORKING_ACTIONS[0]
        RAISE_ACTION = WORKING_ACTIONS[1] if len(WORKING_ACTIONS) > 1 else WORKING_ACTIONS[0]
    print(f"✅ Hoạt động: {WORKING_ACTIONS}")
    print(f"🎯 WAVE={WAVE_ACTION}  RAISE={RAISE_ACTION}")


def _lamp_breath(speed: str = "mid", color: str = "green") -> None:
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
    asyncio.create_task(PlayExpression(is_serial=False, express_name=name).execute())


def _say(text: str) -> None:
    asyncio.create_task(StartPlayTTS(is_serial=False, text=text).execute())


async def _act(name: str | None) -> None:
    if not name:
        await asyncio.sleep(min(BEAT, 0.5))
        return
    try:
        _, resp = await PlayAction(action_name=name, is_serial=False).execute()
        if resp and getattr(resp, "isSuccess", False):
            await asyncio.sleep(0.15)
    except Exception:
        await asyncio.sleep(0.2)


async def _go(direction: int, steps: int = 1) -> None:
    dmap = {
        1: MoveRobotDirection.FORWARD,
        2: MoveRobotDirection.BACKWARD,
        3: MoveRobotDirection.LEFTWARD,
        4: MoveRobotDirection.RIGHTWARD,
    }
    direction = dmap.get(direction, MoveRobotDirection.FORWARD)
    try:
        await MoveRobot(is_serial=False, direction=direction, step=steps).execute()
    except Exception:
        pass
    await asyncio.sleep(STAB)


def set_pattern(name: str) -> None:
    global _current_pattern
    if name in PATTERNS:
        _current_pattern = name


# --- Patterns (1 bar ~ FOUR) ---
async def pattern_groove() -> None:
    await _go(3)
    await asyncio.sleep(HALF)
    await _act(WAVE_ACTION)
    await asyncio.sleep(HALF)
    await _go(4)
    await asyncio.sleep(HALF)
    await _act(WAVE_ACTION)
    await asyncio.sleep(HALF)


async def pattern_sway() -> None:
    await _go(3)
    await asyncio.sleep(BEAT)
    await _go(4)
    await asyncio.sleep(BEAT)
    await _go(3)
    await asyncio.sleep(BEAT)
    await _go(4)
    await asyncio.sleep(BEAT)


async def pattern_wave_sway() -> None:
    await _act(WAVE_ACTION)
    await asyncio.sleep(BEAT)
    await _go(3)
    await asyncio.sleep(HALF)
    await _act(WAVE_ACTION)
    await asyncio.sleep(BEAT)
    await _go(4)
    await asyncio.sleep(HALF)


async def pattern_raise_groove() -> None:
    await _act(RAISE_ACTION)
    await asyncio.sleep(TWO)
    await _go(3)
    await asyncio.sleep(HALF)
    await _go(4)
    await asyncio.sleep(HALF)


async def pattern_forward_groove() -> None:
    await _go(1)
    await asyncio.sleep(HALF)
    await _act(WAVE_ACTION)
    await asyncio.sleep(BEAT)
    await _go(2)
    await asyncio.sleep(HALF)
    await _act(WAVE_ACTION)
    await asyncio.sleep(BEAT)


PATTERNS: dict[str, object] = {
    "groove": pattern_groove,
    "sway": pattern_sway,
    "wave_sway": pattern_wave_sway,
    "raise_groove": pattern_raise_groove,
    "forward_groove": pattern_forward_groove,
}


async def dance_loop() -> None:
    global _running
    while _running:
        fn = PATTERNS.get(_current_pattern, pattern_groove)
        await fn()  # type: ignore[misc]


async def sleep_until(target_sec: float, t0: float) -> None:
    rem = target_sec - (time.time() - t0)
    if rem > 0.1:
        await asyncio.sleep(rem)


# --- Timeline bài 1 ---
async def timeline_o_i_i(t0: float) -> None:
    set_pattern("groove")
    _lamp_breath("slow", "green")
    _face("codemao1")

    await sleep_until(10, t0)
    set_pattern("sway")
    _lamp_breath("mid", "green")

    await sleep_until(25, t0)
    set_pattern("forward_groove")
    _lamp_breath("mid", "green")

    await sleep_until(35, t0)
    set_pattern("wave_sway")
    _lamp_breath("fast", "green")
    _say("Ô i i!")

    await sleep_until(45, t0)
    set_pattern("raise_groove")
    _lamp_breath("fast", "red")

    await sleep_until(55, t0)
    set_pattern("groove")
    _lamp_breath("slow", "green")

    await sleep_until(70, t0)
    set_pattern("forward_groove")
    _lamp_breath("mid", "green")

    await sleep_until(80, t0)
    set_pattern("wave_sway")
    _lamp_breath("fast", "green")
    _say("Ộ i i! Alo Vũ!")

    await sleep_until(95, t0)
    set_pattern("sway")
    _lamp_breath("slow", "green")

    await sleep_until(110, t0)
    set_pattern("raise_groove")
    _lamp_breath("fast", "red")
    _say("Ộ i i! Alo Vũ Mixi!")

    await sleep_until(140, t0)
    set_pattern("groove")
    _lamp_breath("slow", "green")
    _face("codemao1")

    await sleep_until(155, t0)


# --- Timeline bài 2 ---
async def timeline_na_na(t0: float) -> None:
    set_pattern("groove")
    _lamp_breath("mid", "green")
    _face("codemao1")

    await sleep_until(19, t0)
    set_pattern("wave_sway")
    _say("Phùng Thanh Độ!")
    _lamp_breath("mid", "green")

    await sleep_until(22, t0)
    set_pattern("groove")

    await sleep_until(26, t0)
    set_pattern("raise_groove")
    _lamp_breath("fast", "green")
    _say("Yê!")

    await sleep_until(29, t0)
    set_pattern("wave_sway")
    _lamp_breath("mid", "green")

    await sleep_until(38, t0)
    set_pattern("forward_groove")
    _lamp_breath("mid", "red")
    _say("Nà ná na na!")

    await sleep_until(44, t0)
    set_pattern("groove")
    _lamp_breath("slow", "green")

    await sleep_until(52, t0)
    set_pattern("sway")

    await sleep_until(56, t0)
    set_pattern("forward_groove")
    _lamp_breath("mid", "green")

    await sleep_until(64, t0)
    set_pattern("wave_sway")
    _lamp_breath("mid", "green")
    _say("Độ Mixi!")

    await sleep_until(70, t0)
    set_pattern("raise_groove")
    _lamp_breath("fast", "red")
    _say("Yê! Mixi!")

    await sleep_until(74, t0)
    set_pattern("groove")
    _lamp_breath("mid", "green")

    await sleep_until(78, t0)
    set_pattern("wave_sway")

    await sleep_until(81, t0)
    set_pattern("forward_groove")
    _lamp_breath("mid", "green")

    await sleep_until(85, t0)
    set_pattern("groove")

    await sleep_until(88, t0)
    set_pattern("wave_sway")
    _lamp_breath("mid", "green")

    await sleep_until(92, t0)
    set_pattern("raise_groove")
    _lamp_breath("fast", "green")
    _say("Yê!")

    await sleep_until(95, t0)
    set_pattern("groove")
    _lamp_breath("slow", "green")
    _face("codemao1")
    _say("Xin chào mọi người!")

    await asyncio.sleep(10)


async def _run_song1(t0: float) -> None:
    global _running
    await timeline_o_i_i(t0)
    _running = False


async def _run_song2(t0: float) -> None:
    global _running
    await timeline_na_na(t0)
    _running = False


async def _play_track(url: str) -> None:
    if not url.startswith("http"):
        print(f"⚠️  URL không hợp lệ: {url[:48]}...")
        return
    ok = await MiniSdk.play_online_audio(url)
    if not ok:
        print("⚠️  play_online_audio trả về False.")


async def perform_two_songs() -> None:
    global _running

    u1, u2 = _url_song1(), _url_song2()

    print("\n🎵 Bài 1: Ộ I I...")
    if u1:
        asyncio.create_task(_play_track(u1))
    else:
        print("⚠️  Thiếu URL bài 1 (O_I_I_MP3_URL / DUAL_URL_O_I_I).")

    t1 = time.time()
    _running = True
    set_pattern("groove")
    await asyncio.gather(dance_loop(), _run_song1(t1))

    print("\n🎵 Bài 2: Nà Ná Na Na...")
    try:
        from mini import mini_sdk

        await mini_sdk.stop_audio()
    except Exception:
        pass
    await asyncio.sleep(0.5)

    asyncio.create_task(_play_track(u2))
    t2 = time.time()
    _running = True
    set_pattern("groove")
    await asyncio.gather(dance_loop(), _run_song2(t2))

    print("✅ Xong cả 2 bài!")


async def main() -> None:
    global WAVE_ACTION, RAISE_ACTION, WORKING_ACTIONS
    _ensure_utf8_stdio()
    MiniSdk.set_log_level(logging.WARNING)
    _set_robot_type_from_env()

    print(f"🔌 Kết nối (serial={SERIAL!r}, ROBOT_IP={'có' if ROBOT_IP else 'dùng mDNS'})...")
    device: WiFiDevice | None
    if ROBOT_IP:
        device = WiFiDevice(name="AlphaMini", address=ROBOT_IP)
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
        await MiniSdk.enter_program()
    except Exception:
        pass
    await asyncio.sleep(1.0)

    skip = _env_bool("DUAL_SKIP_DISCOVER", default=bool(ROBOT_IP))
    if skip:
        apply_preset_actions()
    else:
        await discover_actions()
    if not WORKING_ACTIONS:
        print("⚠️  Chưa có action — vẫn thử nhảy (MoveRobot + _act an toàn).")
    if WAVE_ACTION is None:
        WAVE_ACTION = "018"
    if RAISE_ACTION is None:
        RAISE_ACTION = "017"

    try:
        await perform_two_songs()
    except asyncio.CancelledError:
        stop_dual_song_dance()
        raise
    except Exception as e:
        print(f"❌ Lỗi: {e}")
    finally:
        stop_dual_song_dance()
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
