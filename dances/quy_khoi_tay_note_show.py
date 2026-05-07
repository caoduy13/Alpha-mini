from __future__ import annotations

import asyncio
import logging
import os
import time

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import mini.mini_sdk as MiniSdk
from mini import MoveRobotDirection
from mini.apis.api_action import MoveRobot, PlayAction, StopAllAction
from mini.apis.api_expression import MouthLampColor, MouthLampMode, PlayExpression, SetMouthLamp
from mini.apis.api_sound import StartPlayTTS
from mini.dns.dns_browser import WiFiDevice

SERIAL = os.getenv("ALPHA_SERIAL", "00018")
ROBOT_TYPE = (os.getenv("ALPHA_ROBOT_TYPE", "edu") or "edu").strip().lower()
def _default_mp3_url() -> str:
    u = (os.getenv("QUY_KHOI_MP3_URL") or os.getenv("AN_DO_MIXI_MP3_URL") or "").strip()
    if u:
        return u
    return "https://drive.google.com/uc?export=download&id=1sC1aNXJALEiUFyyhoW3J-j3lyDS5JyLX"


ACTION_WAVE = os.getenv("ALPHA_ACTION_WAVE", "018")
ACTION_RAISE = os.getenv("ALPHA_ACTION_RAISE", "017")

BEAT_ANIME = 0.43

_pattern = "boll_sway"
_running = True


def stop_quy_khoi_dance() -> None:
    global _running
    _running = False


def _set_robot_type(name: str) -> None:
    if name in ("edu",):
        MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)
    elif name in ("mini", "min"):
        MiniSdk.set_robot_type(MiniSdk.RobotType.MINI)
    elif name in ("dedu", "cn", "china"):
        MiniSdk.set_robot_type(MiniSdk.RobotType.DEDU)
    elif name in ("kor", "kr"):
        MiniSdk.set_robot_type(MiniSdk.RobotType.KOR)
    else:
        MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)


async def safe_action(name: str | None, wait: float = 0.2, fallback_move=None):
    if not name:
        if fallback_move:
            await fallback_move()
        return
    try:
        result = await PlayAction(is_serial=True, action_name=name).execute()
        ok = isinstance(result, tuple) and len(result) == 2 and bool(getattr(result[1], "isSuccess", False))
        if not ok and isinstance(result, tuple) and len(result) == 2 and getattr(result[1], "resultCode", None) == -2:
            if fallback_move:
                await fallback_move()
    except Exception:
        if fallback_move:
            await fallback_move()
    await asyncio.sleep(wait)


async def _L(stab: float = 0.35):
    await MoveRobot(is_serial=False, direction=MoveRobotDirection.LEFTWARD, step=1).execute()
    await asyncio.sleep(stab)


async def _R(stab: float = 0.35):
    await MoveRobot(is_serial=False, direction=MoveRobotDirection.RIGHTWARD, step=1).execute()
    await asyncio.sleep(stab)


async def _F(stab: float = 0.45):
    await MoveRobot(is_serial=False, direction=MoveRobotDirection.FORWARD, step=1).execute()
    await asyncio.sleep(stab)


async def _B(stab: float = 0.45):
    await MoveRobot(is_serial=False, direction=MoveRobotDirection.BACKWARD, step=1).execute()
    await asyncio.sleep(stab)


async def _W():
    await safe_action(ACTION_WAVE, fallback_move=_L)


async def _UP():
    await safe_action(ACTION_RAISE, fallback_move=_R)


def _say(text: str):
    asyncio.create_task(StartPlayTTS(is_serial=False, text=text).execute())


def _face(mood: str):
    faces = {
        "happy": "codemao1",
        "surprised": "codemao3",
        "cool": "codemao2",
        "excited": "codemao4",
    }
    asyncio.create_task(PlayExpression(is_serial=False, express_name=faces.get(mood, "codemao1")).execute())


def _lamp(speed: str = "mid", color: str = "green"):
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


async def anime_power():
    await _F()
    await _UP()
    await _B()
    await _W()


async def anime_strafe():
    await _L()
    await _L()
    await _R()
    await _R()


async def anime_stand_strong():
    await _UP()
    await asyncio.sleep(BEAT_ANIME * 2)
    await _W()
    await asyncio.sleep(BEAT_ANIME * 2)


async def anime_march():
    await _F()
    await _R()
    await _F()
    await _L()


async def boll_sway():
    await _L()
    await _W()
    await _R()
    await _W()


async def boll_circle():
    await _L()
    await _F()
    await _R()
    await _B()


async def boll_wave_pulse():
    await _W()
    await _W()
    await _L()
    await _W()


async def boll_celebrate():
    await _UP()
    await _L()
    await _UP()
    await _R()


PATTERN_MAP = {
    "anime_power": anime_power,
    "anime_strafe": anime_strafe,
    "anime_stand": anime_stand_strong,
    "anime_march": anime_march,
    "boll_sway": boll_sway,
    "boll_circle": boll_circle,
    "boll_wave": boll_wave_pulse,
    "boll_celebrate": boll_celebrate,
}


def switch(name: str):
    global _pattern
    _pattern = name
    print(f"  -> {name}")


async def dance_loop():
    global _running
    while _running:
        fn = PATTERN_MAP.get(_pattern, boll_sway)
        await fn()


async def music_timeline(t0: float):
    global _running

    async def at(sec: float):
        rem = sec - (time.time() - t0)
        if rem > 0:
            await asyncio.sleep(rem)

    switch("anime_stand")
    _lamp("fast")
    _face("cool")

    await at(8.0)
    switch("anime_power")
    _lamp("mid")
    _face("surprised")
    _say("Quỷ Khói!")

    await at(14.0)
    switch("anime_strafe")
    _face("cool")

    await at(20.0)
    switch("boll_sway")
    _lamp("slow")
    _face("happy")
    _say("Nà ná na na anh Phùng Thanh Độ!")

    await at(26.0)
    switch("boll_celebrate")
    _say("Anh Độ Mixi!")

    await at(29.0)
    switch("boll_wave")
    await _UP()
    _lamp("fast")
    _say("Yeeeeee!")

    await at(35.0)
    switch("anime_march")
    _lamp("mid")
    _face("cool")
    _say("Tày Note!")

    await at(42.0)
    switch("anime_strafe")
    _face("surprised")

    await at(50.0)
    switch("boll_sway")
    _lamp("slow")
    _face("happy")
    _say("Nà ná na na!")

    await at(56.0)
    switch("boll_circle")
    _say("Anh Độ Mixi!")

    await at(61.0)
    switch("boll_celebrate")
    await _UP()
    _lamp("fast")
    _say("Yeeeeee Mixi!")

    await at(65.0)
    switch("anime_power")
    _lamp("fast")
    _face("cool")

    await at(72.0)
    switch("anime_strafe")
    _face("surprised")

    await at(78.0)
    switch("anime_stand")
    await _UP()
    _say("Quỷ Khói! Tày Note!")

    await at(80.0)
    switch("boll_celebrate")
    _lamp("fast")
    _face("excited")
    _say("Nà ná na na anh Phùng Thanh Độ!")

    await at(86.0)
    switch("boll_sway")
    _say("Anh Độ Mixi!")

    await at(90.0)
    switch("boll_circle")
    _say("Yeeeeee!")

    await at(95.0)
    switch("boll_wave")
    _face("happy")
    _lamp("slow")
    _say("Cảm ơn mọi người! Nà ná na na!")

    await asyncio.sleep(5)
    _running = False
    print("Timeline kết thúc.")


async def _play_audio_bg(url: str):
    ok = await MiniSdk.play_online_audio(url)
    if not ok:
        print("WARN: play_online_audio trả về False.")


async def perform(mp3_url: str | None = None):
    global _running, _pattern
    _running = True
    _pattern = "boll_sway"

    print("Quỷ Khói & Tày Note — Độ Mixi ft. Mappa")
    print("=" * 50)

    url = (mp3_url or _default_mp3_url()).strip()
    if url.startswith("http://") or url.startswith("https://"):
        asyncio.create_task(_play_audio_bg(url))

    t0 = time.time()
    await asyncio.gather(dance_loop(), music_timeline(t0))
    print("=" * 50)
    print("Xong! Nà ná na na~")


async def run_quy_khoi_show() -> None:
    """Gọi từ server sau MiniSdk.connect (cùng session với AlphaMiniClient)."""
    try:
        await perform()
    finally:
        stop_quy_khoi_dance()


async def main():
    MiniSdk.set_log_level(logging.WARNING)
    _set_robot_type(ROBOT_TYPE)

    print(f"Tìm Alpha Mini serial={SERIAL} ...")
    device: WiFiDevice = await MiniSdk.get_device_by_name(SERIAL, 15)
    if not device:
        print("Không tìm thấy robot.")
        return

    ok = await MiniSdk.connect(device)
    if not ok:
        print("Kết nối robot thất bại.")
        return

    await MiniSdk.enter_program()
    await asyncio.sleep(2)
    print(f"Đã kết nối: {device}")
    try:
        await perform()
    finally:
        try:
            await StopAllAction(is_serial=False).execute()
        except Exception:
            pass
        await asyncio.sleep(1)
        await MiniSdk.release()


if __name__ == "__main__":
    asyncio.run(main())
