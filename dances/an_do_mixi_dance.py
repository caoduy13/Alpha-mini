# pyright: reportMissingImports=false
# ═══════════════════════════════════════════════════════════════
#  Alpha Mini — Ấn Độ Mixi v4
#  Nhảy liên tục (groove loop) + timeline đổi pattern / TTS không block
#  SDK: MoveRobot(is_serial,…), PlayExpression(express_name=…), …
# ═══════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

from dotenv import load_dotenv

load_dotenv()


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


import mini.mini_sdk as MiniSdk
from mini.dns.dns_browser import WiFiDevice
from mini.apis.api_action import MoveRobot, PlayAction, StopAllAction
from mini import MoveRobotDirection
from mini.apis.api_sound import StartPlayTTS
from mini.apis.api_expression import (
    PlayExpression,
    SetMouthLamp,
    MouthLampColor,
    MouthLampMode,
)

_DRIVE_FILE_ID = "1sC1aNXJALEiUFyyhoW3J-j3lyDS5JyLX"
DEFAULT_MIXI_MP3_URL = (
    f"https://drive.google.com/uc?export=download&id={_DRIVE_FILE_ID}"
)

BEAT = 0.47
TWO = 0.94
FOUR = 1.88

_current_pattern = "basic"
_running = False


def stop_mixi_dance() -> None:
    """Dừng vòng groove v4 (gọi khi có lệnh robot mới từ server)."""
    global _running
    _running = False


def _music_lead_sec() -> float:
    try:
        return max(0.0, float(os.getenv("AN_DO_MIXI_MUSIC_LEAD_SEC", "1.2")))
    except ValueError:
        return 1.2


def fire_say(text: str) -> None:
    """TTS không chặn groove loop."""
    asyncio.create_task(StartPlayTTS(is_serial=False, text=text).execute())


def fire_lamp(speed: str = "slow") -> None:
    dur = 1880 if speed == "slow" else 470

    async def _run() -> None:
        await SetMouthLamp(
            is_serial=False,
            mode=MouthLampMode.BREATH,
            color=MouthLampColor.GREEN,
            duration=6000,
            breath_duration=dur,
        ).execute()

    asyncio.create_task(_run())


async def _left() -> None:
    await MoveRobot(
        is_serial=False, direction=MoveRobotDirection.LEFTWARD, step=1
    ).execute()
    await asyncio.sleep(0.3)


async def _right() -> None:
    await MoveRobot(
        is_serial=False, direction=MoveRobotDirection.RIGHTWARD, step=1
    ).execute()
    await asyncio.sleep(0.3)


async def _forward() -> None:
    await MoveRobot(
        is_serial=False, direction=MoveRobotDirection.FORWARD, step=1
    ).execute()
    await asyncio.sleep(0.4)


async def _backward() -> None:
    await MoveRobot(
        is_serial=False, direction=MoveRobotDirection.BACKWARD, step=1
    ).execute()
    await asyncio.sleep(0.4)


async def _wave() -> None:
    await PlayAction(is_serial=True, action_name="018").execute()
    await asyncio.sleep(0.2)


async def _raise() -> None:
    await PlayAction(is_serial=True, action_name="017").execute()
    await asyncio.sleep(0.2)


async def _happy() -> None:
    await PlayExpression(is_serial=False, express_name="codemao1").execute()


async def _surprised() -> None:
    await PlayExpression(is_serial=False, express_name="codemao3").execute()


async def groove_basic() -> None:
    await _left()
    await _wave()
    await _right()
    await _wave()


async def groove_forward_back() -> None:
    await _forward()
    await _wave()
    await _backward()
    await _wave()


async def groove_wave_only() -> None:
    await _wave()
    await _wave()
    await _wave()
    await _wave()


async def groove_left_heavy() -> None:
    await _left()
    await _left()
    await _wave()
    await _right()


async def groove_right_heavy() -> None:
    await _right()
    await _right()
    await _wave()
    await _left()


async def groove_yee() -> None:
    await _surprised()
    fire_lamp("fast")
    await _raise()
    await _wave()
    await _happy()
    fire_lamp("slow")


def set_pattern(name: str) -> None:
    global _current_pattern
    _current_pattern = name
    print(f"  -> Pattern: {name}")


async def dance_loop() -> None:
    global _running
    pattern_map = {
        "basic": groove_basic,
        "forward_back": groove_forward_back,
        "wave_only": groove_wave_only,
        "left_heavy": groove_left_heavy,
        "right_heavy": groove_right_heavy,
        "yee": groove_yee,
    }
    while _running:
        fn = pattern_map.get(_current_pattern, groove_basic)
        await fn()


async def music_timeline(t0: float) -> None:
    global _running

    def elapsed() -> float:
        return time.time() - t0

    async def sleep_until(target: float) -> None:
        remaining = target - elapsed()
        if remaining > 0:
            await asyncio.sleep(remaining)

    set_pattern("basic")
    fire_lamp("slow")
    await _happy()

    await sleep_until(19.0)
    fire_say("Phùng Thanh Độ!")
    set_pattern("wave_only")

    await sleep_until(22.5)
    fire_say("Anh Độ Mixi!")
    set_pattern("left_heavy")

    await sleep_until(26.0)
    fire_say("Yeeeeee!")
    set_pattern("yee")

    await sleep_until(29.0)
    fire_say("Anh Độ Mixi!")
    set_pattern("basic")

    await sleep_until(32.0)
    fire_say("Anh Độ Mixi!")
    set_pattern("right_heavy")

    await sleep_until(35.0)
    fire_say("Anh Độ Mixi!")
    set_pattern("forward_back")

    await sleep_until(38.0)
    fire_say("Anh tên là anh Độ, anh Độ Mixi nà nà!")
    set_pattern("basic")

    await sleep_until(44.0)
    fire_say("Cảm ơn anh vì đã mang lại tiếng cười!")
    set_pattern("wave_only")

    await sleep_until(52.0)
    fire_say("Cảm ơn anh vì những bữa cơm!")
    set_pattern("left_heavy")

    await sleep_until(56.0)
    fire_say("Anh mời các em đi chơi, đi quẩy!")
    set_pattern("forward_back")

    await sleep_until(64.0)
    fire_say("Nhưng em vẫn thích anh Độ Mixi!")
    set_pattern("basic")

    await sleep_until(70.0)
    fire_say("Yeeeeee Mixiiii!")
    set_pattern("yee")

    await sleep_until(74.0)
    fire_say("Anh Độ Mixi!")
    set_pattern("right_heavy")

    await sleep_until(78.0)
    fire_say("Anh tên là Thanh Độ!")
    set_pattern("left_heavy")

    await sleep_until(81.0)
    fire_say("Mọi người hay gọi anh Độ Mixi!")
    set_pattern("basic")

    await sleep_until(85.0)
    fire_say("Anh tên là Thanh Độ!")
    set_pattern("right_heavy")

    await sleep_until(88.0)
    fire_say("Mọi người hay gọi anh Độ Mixi!")
    set_pattern("forward_back")

    await sleep_until(92.0)
    fire_say("Yeeeeeee!")
    set_pattern("yee")

    await sleep_until(95.0)
    fire_say("Anh Độ Mixi! Cảm ơn mọi người!")
    set_pattern("wave_only")

    await asyncio.sleep(5)
    _running = False
    print("Timeline ket thuc!")


async def _play_audio_bg(url: str) -> None:
    ok = await MiniSdk.play_online_audio(url)
    if not ok:
        print("WARN: play_online_audio tra ve False.")


async def perform_mixi_v4(mp3_url: str | None) -> None:
    """v4: gather(dance_loop, music_timeline)."""
    global _running, _current_pattern

    _running = True
    _current_pattern = "basic"

    print("An Do Mixi v4 — nhay lien tuc + timeline")
    print("=" * 50)

    if mp3_url and mp3_url.strip().lower().startswith("http"):
        u = mp3_url.strip()
        print(f"Nhac: {u[:72]}...")
        lead = _music_lead_sec()
        t0 = time.time() - lead
        asyncio.create_task(_play_audio_bg(u))
        await asyncio.sleep(0)
    else:
        print("Khong co URL mp3 — chi vu dao.")
        t0 = time.time()

    try:
        await asyncio.gather(
            dance_loop(),
            music_timeline(t0),
        )
    except asyncio.CancelledError:
        print("Mixi: huy (lenh moi).")
        raise
    finally:
        stop_mixi_dance()

    print("=" * 50)
    print("Hoan thanh! Na na na na~")


def _resolve_mp3_url() -> str | None:
    env = (os.getenv("AN_DO_MIXI_MP3_URL") or "").strip()
    if env:
        return env
    return DEFAULT_MIXI_MP3_URL


async def run_mixi_show() -> None:
    """Gọi từ server khi đã MiniSdk.connect."""
    await perform_mixi_v4(_resolve_mp3_url())


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


async def main() -> None:
    _ensure_utf8_stdio()
    MiniSdk.set_log_level(logging.WARNING)
    _set_robot_type_from_env()

    robot_ip = (os.getenv("ROBOT_IP") or "").strip()
    if not robot_ip:
        print("Thieu ROBOT_IP trong .env")
        sys.exit(1)

    mp3_url = _resolve_mp3_url()
    print(f"Ket noi Alpha Mini @ {robot_ip} ...")

    device = WiFiDevice(name="AlphaMini", address=robot_ip)
    if not await MiniSdk.connect(device):
        print("Khong ket noi duoc robot.")
        sys.exit(1)

    await MiniSdk.enter_program()
    await asyncio.sleep(2)

    try:
        await perform_mixi_v4(mp3_url)
    except Exception as e:
        print(f"Loi: {e}")
        raise
    finally:
        global _running
        _running = False
        try:
            await StopAllAction(is_serial=False).execute()
        except Exception:
            pass
        await asyncio.sleep(1)
        await MiniSdk.release()
        print("Da ngat ket noi.")


if __name__ == "__main__":
    asyncio.run(main())
