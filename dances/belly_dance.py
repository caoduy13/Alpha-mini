# pyright: reportMissingImports=false
"""
Belly dance — Alpha Mini (UBTECH SDK alphamini).
Nhảy liên tục (dance_loop + music_timeline), tự detect action, fallback MoveRobot khi -2.
Nhạc nền mặc định: bài “nà ná na na” (Drive) — có thể đổi bằng BELLY_DANCE_MP3_URL.

Chạy: python belly_dance.py
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

# ── Cấu hình robot / nhạc ───────────────────────────────────
SERIAL = (os.getenv("ALPHA_SERIAL") or "00018").strip()
ROBOT_IP = (os.getenv("ROBOT_IP") or "").strip()
# 1 beat belly ~100 BPM → ~0.60s; spec gợi ý 0.47 (giữ nhịp mượt, luôn < 0.5s rule)
BEAT = float(os.getenv("BELLY_BEAT_SEC", "0.47"))
MAX_SLEEP_IN_PATTERN = float(os.getenv("BELLY_MAX_PATTERN_SLEEP", "0.5"))


def _default_mp3_url() -> str:
    u = (
        os.getenv("BELLY_DANCE_MP3_URL")
        or os.getenv("AN_DO_MIXI_MP3_URL")
        or os.getenv("QUY_KHOI_MP3_URL")
        or ""
    ).strip()
    if u:
        return u
    return "https://drive.google.com/uc?export=download&id=1sC1aNXJALEiUFyyhoW3J-j3lyDS5JyLX"


MP3_URL = _default_mp3_url()

# Action candidates (inner id) — quét firmware
_ACTION_CANDIDATES = [
    f"{i:03d}" for i in range(1, 29)
]

# Ưu tiên gán vai trò theo mã thường gặp; chỉ dùng nếu có trong working
_ROLE_PREFERS: list[tuple[str, str]] = [
    ("wave", "018"),
    ("raise_arms", "017"),
    ("bow", "016"),
    ("sway_left", "014"),
    ("sway_right", "015"),
    ("spin", "012"),
    ("pose", "010"),
    ("shimmy", "013"),
]

# Global sau detect — detect_working_actions() gán đầy đủ key
ROLES: dict[str, str | None] = {}

WORKING_IDS: list[str] = []
_current_pattern = "gentle_sway"
_running = True
_t0_perf: float = 0.0


def stop_belly_dance() -> None:
    """Dừng vòng nhảy (gọi từ code khác nếu cần)."""
    global _running
    _running = False


def _stab() -> float:
    """Stabilize sau bước — luôn <= MAX_SLEEP_IN_PATTERN."""
    return min(BEAT, MAX_SLEEP_IN_PATTERN - 0.02)


def _log_pattern(tag: str, mood: str, lamp: str) -> None:
    """In log có dấu thời gian từ lúc bắt nhạc."""
    elapsed = time.perf_counter() - _t0_perf
    m, s = int(elapsed // 60), int(elapsed % 60)
    lamp_emoji = {"slow": "💚 slow", "mid": "💚 mid", "fast": "💚 fast"}.get(lamp, lamp)
    print(f"🕐 [{m}:{s:02d}] {tag:18s} → {lamp_emoji} ({mood})")


# ═══════════════ BƯỚC 1: AUTO-DETECT ══════════════════════════


async def detect_working_actions() -> dict[str, str | None]:
    """
    Thử từng mã action; trả về ROLES đã gán.
    Chạy một lần khi khởi động (không nằm trong dance_loop).
    """
    global WORKING_IDS, ROLES
    working: list[str] = []
    print("🔍 Detecting actions...")
    for name in _ACTION_CANDIDATES:
        try:
            _, resp = await PlayAction(action_name=name, is_serial=True).execute()
            if resp and getattr(resp, "isSuccess", False):
                working.append(name)
                await asyncio.sleep(min(1.5, 1.2))
            else:
                await asyncio.sleep(0.2)
        except Exception:
            await asyncio.sleep(0.2)

    WORKING_IDS = list(working)
    wset = set(working)
    roles: dict[str, str | None] = {}

    for role, aid in _ROLE_PREFERS:
        if aid in wset:
            roles[role] = aid

    used = {v for v in roles.values() if v}
    remaining = [x for x in working if x not in used]
    i = 0
    for role in [
        "wave",
        "raise_arms",
        "bow",
        "sway_left",
        "sway_right",
        "spin",
        "pose",
        "shimmy",
    ]:
        if roles.get(role) is None and i < len(remaining):
            roles[role] = remaining[i]
            i += 1

    ROLES.clear()
    ROLES.update(roles)
    print(f"✅ Detected {len(working)} actions: {working}")
    print(f"✅ Role mapping: { {k: v for k, v in ROLES.items() if v} }")
    return ROLES


# ═══════════════ SAFE ACTION (fallback -2 / lỗi) ═══════════════


async def safe_play_action(
    role_key: str,
    wait: float | None = None,
    *,
    fallback=None,
) -> None:
    """
    PlayAction trong nhảy: is_serial=False (khớp server, tránh tắc serial).
    resultCode -2 hoặc lỗi → fallback MoveRobot.
    """
    name = ROLES.get(role_key)
    w = wait if wait is not None else min(0.2, _stab() * 0.4)
    if not name:
        if fallback:
            await fallback()
        return
    try:
        result = await PlayAction(action_name=name, is_serial=False).execute()
        ok = (
            isinstance(result, tuple)
            and len(result) == 2
            and bool(getattr(result[1], "isSuccess", False))
        )
        if not ok and fallback:
            await fallback()
    except Exception:
        if fallback:
            await fallback()
    await asyncio.sleep(min(w, MAX_SLEEP_IN_PATTERN))


# ═══════════════ BƯỚC 2: ATOMIC MOVES (mỗi bước ~1 beat) ══════════


async def _L(stab: float | None = None) -> None:
    sb = min(stab if stab is not None else _stab(), MAX_SLEEP_IN_PATTERN)
    await MoveRobot(is_serial=False, direction=MoveRobotDirection.LEFTWARD, step=1).execute()
    await asyncio.sleep(sb)


async def _R(stab: float | None = None) -> None:
    sb = min(stab if stab is not None else _stab(), MAX_SLEEP_IN_PATTERN)
    await MoveRobot(is_serial=False, direction=MoveRobotDirection.RIGHTWARD, step=1).execute()
    await asyncio.sleep(sb)


async def _F(stab: float | None = None) -> None:
    sb = min(stab if stab is not None else _stab(), MAX_SLEEP_IN_PATTERN)
    await MoveRobot(is_serial=False, direction=MoveRobotDirection.FORWARD, step=1).execute()
    await asyncio.sleep(sb)


async def _B(stab: float | None = None) -> None:
    sb = min(stab if stab is not None else _stab(), MAX_SLEEP_IN_PATTERN)
    await MoveRobot(is_serial=False, direction=MoveRobotDirection.BACKWARD, step=1).execute()
    await asyncio.sleep(sb)


async def _W() -> None:
    await safe_play_action("wave", fallback=lambda: _L())


async def _UP() -> None:
    await safe_play_action("raise_arms", fallback=lambda: _R())


async def _BOW() -> None:
    async def bow_fb() -> None:
        await _B(stab=min(0.35, MAX_SLEEP_IN_PATTERN))
        await _F(stab=min(0.35, MAX_SLEEP_IN_PATTERN))

    await safe_play_action("bow", fallback=bow_fb)


async def _SPIN() -> None:
    async def spin_fb() -> None:
        q = min(0.28, MAX_SLEEP_IN_PATTERN)
        await _L(stab=q)
        await _R(stab=q)
        await _L(stab=q)
        await _R(stab=q)

    await safe_play_action("spin", fallback=spin_fb)


# ═══════════════ BƯỚC 3: PATTERNS (12 bars × 4 beat) ═══════════


async def gentle_sway() -> None:
    await _L()
    await _W()
    await _R()
    await _W()


async def gentle_wave() -> None:
    await _W()
    await _W()
    await _L()
    await _R()


async def gentle_step() -> None:
    await _F()
    await _W()
    await _B()
    await _W()


async def gentle_circle() -> None:
    await _L()
    await _F()
    await _R()
    await _B()


async def rhythmic_pulse() -> None:
    await _L()
    await _UP()
    await _R()
    await _UP()


async def rhythmic_cross() -> None:
    await _L()
    await _R()
    await _L()
    await _W()


async def rhythmic_march() -> None:
    await _F()
    await _W()
    await _F()
    await _W()


async def rhythmic_retreat() -> None:
    await _B()
    await _W()
    await _B()
    await _W()


async def express_spin() -> None:
    await _SPIN()
    await _W()
    await _L()
    await _R()


async def express_pose() -> None:
    await _UP()
    await _BOW()
    await _UP()
    await _W()


async def express_shimmy() -> None:
    q = min(0.38, MAX_SLEEP_IN_PATTERN)
    await _L(q)
    await _L(q)
    await _R(q)
    await _R(q)


async def express_finale() -> None:
    await _UP()
    await _SPIN()
    await _W()
    await _BOW()


PATTERN_MAP: dict[str, object] = {
    "gentle_sway": gentle_sway,
    "gentle_wave": gentle_wave,
    "gentle_step": gentle_step,
    "gentle_circle": gentle_circle,
    "rhythmic_pulse": rhythmic_pulse,
    "rhythmic_cross": rhythmic_cross,
    "rhythmic_march": rhythmic_march,
    "rhythmic_retreat": rhythmic_retreat,
    "express_spin": express_spin,
    "express_pose": express_pose,
    "express_shimmy": express_shimmy,
    "express_finale": express_finale,
}


def switch_pattern(name: str) -> None:
    global _current_pattern
    _current_pattern = name


# ═══════════════ BƯỚC 4: DANCE ENGINE ═══════════════════════════


async def dance_loop() -> None:
    """Vòng lặp nhảy: mỗi lần một pattern; không sleep thêm ở đây."""
    global _running
    while _running:
        fn = PATTERN_MAP.get(_current_pattern, gentle_sway)
        await fn()  # type: ignore[misc]


# ═══════════════ BƯỚC 5: TIMELINE + BƯỚC 6/7: lamp/face/TTS ══════


def _set_mood(mood: str) -> None:
    """gentle | rhythmic | expressive → lamp + mặt."""
    if mood == "gentle":
        _lamp("slow")
        _face("gentle")
    elif mood == "rhythmic":
        _lamp("mid")
        _face("rhythmic")
    else:
        _lamp("fast")
        _face("expressive")


def _lamp(speed: str = "mid") -> None:
    dur_map = {"slow": 1880, "mid": 800, "fast": 400}
    asyncio.create_task(
        SetMouthLamp(
            is_serial=False,
            color=MouthLampColor.GREEN,
            mode=MouthLampMode.BREATH,
            duration=6000,
            breath_duration=dur_map.get(speed, 800),
        ).execute()
    )


def _face(kind: str) -> None:
    faces = {
        "gentle": "codemao1",
        "rhythmic": "codemao2",
        "expressive": "codemao3",
    }
    name = faces.get(kind, "codemao1")
    asyncio.create_task(PlayExpression(is_serial=False, express_name=name).execute())


def _say(text: str) -> None:
    asyncio.create_task(StartPlayTTS(is_serial=False, text=text).execute())


async def music_timeline(t0: float) -> None:
    """Đổi pattern theo thời gian nhạc (~100 BPM backing)."""

    async def at(sec: float) -> None:
        rem = sec - (time.time() - t0)
        if rem > 0:
            await asyncio.sleep(rem)

    # 0:00 gentle_sway
    switch_pattern("gentle_sway")
    _set_mood("gentle")
    _log_pattern("gentle_sway", "gentle", "slow")
    _say("Nà ná na na — belly dance!")

    await at(8.0)
    switch_pattern("gentle_circle")
    _set_mood("gentle")
    _log_pattern("gentle_circle", "gentle", "slow")

    await at(16.0)
    switch_pattern("rhythmic_pulse")
    _set_mood("rhythmic")
    _log_pattern("rhythmic_pulse", "rhythmic", "mid")

    await at(24.0)
    switch_pattern("rhythmic_cross")
    _set_mood("rhythmic")
    _log_pattern("rhythmic_cross", "rhythmic", "mid")

    await at(32.0)
    switch_pattern("gentle_wave")
    _set_mood("gentle")
    _log_pattern("gentle_wave", "gentle", "slow")

    await at(40.0)
    switch_pattern("rhythmic_march")
    _set_mood("rhythmic")
    _log_pattern("rhythmic_march", "rhythmic", "mid")

    await at(48.0)
    switch_pattern("express_pose")
    _set_mood("expressive")
    _log_pattern("express_pose", "expressive", "fast")

    await at(56.0)
    switch_pattern("express_shimmy")
    _set_mood("expressive")
    _log_pattern("express_shimmy", "expressive", "fast")
    _say("Theo nhịp nà!")

    await at(64.0)
    switch_pattern("gentle_sway")
    _set_mood("gentle")
    _log_pattern("gentle_sway", "gentle", "slow")

    await at(72.0)
    switch_pattern("rhythmic_pulse")
    _set_mood("rhythmic")
    _log_pattern("rhythmic_pulse", "rhythmic", "mid")

    await at(80.0)
    switch_pattern("express_spin")
    _set_mood("expressive")
    _log_pattern("express_spin", "expressive", "fast")

    await at(88.0)
    switch_pattern("express_finale")
    _set_mood("expressive")
    _log_pattern("express_finale", "expressive", "fast")

    await at(95.0)
    switch_pattern("gentle_wave")
    _set_mood("gentle")
    _log_pattern("gentle_wave", "outro", "slow")
    _say("Cảm ơn đã xem!")

    await asyncio.sleep(4)
    global _running
    _running = False
    print("✅ Timeline kết thúc.")


# ═══════════════ BƯỚC 8: PERFORM + MAIN ══════════════════════════


async def _play_music_bg(url: str) -> None:
    if not (url.startswith("http://") or url.startswith("https://")):
        print("⚠️ Không có URL nhạc — chỉ nhảy không.")
        return
    ok = await MiniSdk.play_online_audio(url)
    if not ok:
        print("⚠️ play_online_audio trả về False — kiểm tra URL / mạng robot.")


async def perform() -> None:
    global _running, _current_pattern, _t0_perf
    _running = True
    _current_pattern = "gentle_sway"
    _t0_perf = time.perf_counter()

    print("🎵 BẮT ĐẦU: Belly Dance (nền: nà ná na na)")
    print("=" * 56)

    url = _default_mp3_url()
    asyncio.create_task(_play_music_bg(url))
    wall_t0 = time.time()

    await asyncio.gather(
        dance_loop(),
        music_timeline(wall_t0),
    )
    print("=" * 56)
    print("✅ Hoàn thành!")


def _set_robot_type_from_env() -> None:
    """Giống server: ROBOT_TYPE=mini|edu|dedu|kor (mặc định mini)."""
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


async def main() -> None:
    _ensure_utf8_stdio()
    MiniSdk.set_log_level(logging.WARNING)
    _set_robot_type_from_env()

    print("🔍 Tìm Alpha Mini...")
    device: WiFiDevice | None = await MiniSdk.get_device_by_name(SERIAL, timeout=20)
    if device:
        print(f"   → Quét serial OK: {SERIAL!r}")
    elif ROBOT_IP:
        print(f"   → Không quét được serial, dùng ROBOT_IP={ROBOT_IP}")
        device = WiFiDevice(name="AlphaMini", address=ROBOT_IP)
    else:
        print(f"❌ Không thấy robot serial={SERIAL!r} và không có ROBOT_IP trong .env")
        return

    if not await MiniSdk.connect(device):
        print("❌ Kết nối thất bại.")
        return

    # Vào chương trình robot
    try:
        await MiniSdk.enter_program()
    except Exception:
        pass
    await asyncio.sleep(2)

    short_name = getattr(device, "name", None) or SERIAL
    print(f"✅ Kết nối: {short_name} @ {getattr(device, 'address', '?')}")

    await detect_working_actions()

    try:
        await perform()
    except asyncio.CancelledError:
        stop_belly_dance()
        raise
    except Exception as e:
        print(f"❌ Lỗi: {e}")
    finally:
        stop_belly_dance()
        try:
            await StopAllAction(is_serial=False).execute()
        except Exception:
            pass
        await asyncio.sleep(0.5)
        await MiniSdk.release()
        print("🔌 Đã ngắt kết nối.")


if __name__ == "__main__":
    asyncio.run(main())
