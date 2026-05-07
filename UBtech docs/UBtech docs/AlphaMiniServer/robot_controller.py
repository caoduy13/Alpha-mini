"""
robot_controller.py — Điều khiển Alpha Mini robot
Bọc alphamini SDK: kết nối, TTS, hành động, lắng nghe giọng nói.
"""

import asyncio
import logging
import uuid
from pathlib import Path
from config import ROBOT_SERIAL, ROBOT_IP, SERVER_LOCAL_IP, SERVER_PORT, EMOTION_MAP

log = logging.getLogger("RobotController")

# Cờ để import SDK — chỉ available trên máy có cài alphamini
try:
    import mini.mini_sdk as MiniSdk
    from mini.dns.dns_browser import WiFiDevice
    from mini.apis.api_sound import PlayAudio, AudioStorageType, StopAllAudio, ChangeRobotVolume
    from mini.apis.api_action import PlayAction
    from mini.apis.api_expression import (
        SetMouthLamp, MouthLampColor, MouthLampMode, PlayExpression
    )
    from mini.apis.api_observe import ObserveSpeechRecognise
    from mini.pb2.codemao_speechrecognise_pb2 import SpeechRecogniseResponse
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    log.warning("alphamini SDK not installed — robot features disabled")

# Thư mục lưu file TTS tạm thời
TTS_DIR = Path("static/audio")
TTS_DIR.mkdir(parents=True, exist_ok=True)

# ─── Choreography Sexy Love (T-ara) ───────────────────────────────────────────
# Định nghĩa: (timestamp_giây, action_id, màu_đèn)
# Mỗi tuple = trigger action đúng lúc timestamp tương ứng trong bài nhạc.
# Ánh xạ theo hướng dẫn vũ đạo:
#   fristboot_*  → INTRO (robot khởi động)
#   w_head_*     → cử động đầu
#   speakingAct* → VERSE / PRE-CHORUS (tay + bước chân)
#   dance_0001.. → CHORUS (iconic robot arm)
#   random_short → BRIDGE (chậm, uy nghi)
# Choreography format: (timestamp_s, action_or_list, lamp_color)
# action_or_list: str → một action  |  list[str] → nhiều action bắn song song
# ─────────────────────────────────────────────────────────────────────────────
SEXY_LOVE_CHOREOGRAPHY: list[tuple[float, str | list, str]] = [

    # ══ INTRO (0:00–0:15): Robot power-on ═══════════════════════════════════
    (0.0,   "fristboot_003",                "white"),
    (3.0,   ["w_head_001", "random_short1"],"white"),  # đầu phải + vai trái
    (5.5,   ["w_head_002", "random_short2"],"white"),  # đầu trái + vai phải
    (8.0,   "w_head_001",                   "white"),  # đầu phải lần 2
    (10.0,  "w_head_002",                   "white"),  # đầu trái lần 2
    (12.0,  ["random_short1", "w_head_011"],"white"),  # vai + scan đầu
    (14.0,  "w_stand_001",                  "white"),  # chuẩn bị

    # ══ VERSE 1 (0:15–0:35): bước chân — tay + đầu xen kẽ ══════════════════
    (15.0,  ["speakingAct2", "w_head_012"], "green"),  # bước phải + đầu nhìn theo
    (17.0,  "speakingAct1",                 "green"),
    (18.5,  ["speakingAct4", "w_head_013"], "green"),  # bước trái + đầu nhìn
    (20.5,  "speakingAct3",                 "green"),
    (22.0,  ["speakingAct6", "w_head_003"], "green"),  # tay gập + đầu gật
    (24.0,  "speakingAct7",                 "green"),
    (25.5,  ["speakingAct8", "w_head_004_v"],"green"), # tay trải + đầu nghiêng
    (27.5,  "speakingAct2",                 "green"),
    (28.5,  ["speakingAct4", "w_head_012"], "green"),  # lặp bước phải
    (30.5,  "speakingAct3",                 "green"),
    (31.5,  ["speakingAct6", "w_head_013"], "green"),  # lặp bước trái
    (33.5,  ["speakingAct5", "w_head_011"], "green"),  # build up → pre-chorus

    # ══ PRE-CHORUS (0:35–0:50): nhanh — ấn nút + tay đổi ═══════════════════
    (35.0,  ["speakingAct9",  "w_head_014"],"green"),  # ấn nút + đầu nhìn xuống
    (36.5,  ["speakingAct9",  "w_head_015"],"green"),  # ấn nút lần 2
    (38.0,  ["speakingAct11", "w_head_016"],"green"),  # tay phải lên, trái xuống
    (39.5,  ["speakingAct12", "w_head_017"],"green"),  # đổi tay
    (41.0,  ["speakingAct13", "w_head_003"],"green"),  # chéo tay ngực + nghiêng phải
    (43.0,  ["speakingAct14", "w_head_004_v"],"green"),
    (45.0,  ["w_head_003",   "speakingAct15"],"green"),# đầu nghiêng
    (47.0,  ["w_head_004_v", "speakingAct16"],"green"),
    (49.0,  ["w_stand_002",  "w_head_011"], "green"),  # chuẩn bị chorus

    # ══ CHORUS 1 (0:50–1:14): ⭐ "Tay Máy + Đầu Giật" xen kẽ ═══════════════
    # Mỗi cặp: body action + head jerk song song — đúng chất robot bị kích điện
    (50.0,  ["dance_0001", "w_head_003"],   "red"),    # tay phải giật + đầu phải
    (51.5,  ["dance_0002", "w_head_004_v"], "green"),  # tay trái giật + đầu trái
    (53.5,  ["dance_0003", "w_head_011"],   "red"),    # bước chorus + đầu scan
    (55.5,  ["dance_0001", "w_head_012"],   "green"),  # tay phải lặp + đầu
    (57.5,  ["dance_0002", "w_head_013"],   "red"),    # tay trái lặp + đầu
    (59.5,  ["dance_0003", "w_head_003"],   "green"),  # bước + đầu nghiêng
    (62.0,  ["dance_0001", "w_head_004_v"], "red"),    # tay máy lặp
    (63.5,  ["dance_0002", "w_head_011"],   "green"),
    (65.5,  ["dance_0004", "w_head_014"],   "red"),    # 180° spin + đầu nhìn xuống
    (68.5,  ["dance_0003", "w_head_015"],   "green"),  # bước + đầu nhìn nghiêng

    # ══ TRANSITION (1:10–1:15): nhịp thở trước verse 2 ══════════════════════
    (71.0,  ["speakingAct1", "w_head_016"], "green"),
    (73.0,  ["speakingAct2", "w_head_017"], "green"),
    (74.5,  "w_stand_003",                  "green"),

    # ══ VERSE 2 (1:15–1:30): biến thể — dày, đầu luôn phối hợp ═════════════
    (75.0,  ["speakingAct3", "w_head_012"], "green"),
    (77.0,  ["speakingAct4", "w_head_013"], "green"),
    (78.5,  ["speakingAct5", "w_head_003"], "green"),
    (80.5,  ["speakingAct6", "w_head_004_v"],"green"),
    (82.0,  ["speakingAct7", "w_head_011"], "green"),
    (84.0,  ["speakingAct8", "w_head_012"], "green"),
    (85.5,  ["speakingAct10","w_head_013"], "green"),
    (87.5,  ["speakingAct2", "w_head_014"], "green"),
    (89.0,  ["speakingAct3", "w_head_015"], "green"),
    (91.0,  ["speakingAct4", "w_head_016"], "green"),
    (92.5,  ["speakingAct5", "w_head_017"], "green"),
    (94.0,  ["speakingAct6", "w_head_011"], "green"),

    # ══ PRE-CHORUS 2 (1:30–1:47): build-up dữ dội hơn ═══════════════════════
    (95.5,  ["speakingAct9",  "w_head_014"],"green"),
    (97.0,  ["speakingAct9",  "w_head_015"],"green"),
    (98.5,  ["speakingAct11", "w_head_016"],"green"),
    (100.0, ["speakingAct12", "w_head_017"],"green"),
    (101.5, ["speakingAct13", "w_head_003"],"green"),
    (103.0, ["speakingAct14", "w_head_004_v"],"green"),
    (105.0, ["speakingAct15", "w_head_011"],"green"),
    (106.5, ["speakingAct16", "w_head_012"],"green"),
    (108.0, ["speakingAct17", "w_head_013"],"green"),

    # ══ BRIDGE (1:47–2:02): uy nghi chậm — cả thân lẫn đầu ══════════════════
    (109.0, ["random_short3",  "w_stand_004"],"white"), # tay nâng + pose oai vệ
    (113.0, "random_short3_1",               "white"),  # freeze 4 nhịp
    (116.0, ["w_head_001",    "w_stand_005"],"white"),  # đầu trái + người đứng
    (118.0, ["w_head_002",    "random_short4"],"white"),# đầu phải + tay hạ
    (121.5, "w_stand_006",                   "white"),  # chuẩn bị nổ

    # ══ CHORUS FINAL (2:02–end): TỐI ĐA — tay + đầu combo liên tục ══════════
    (123.0, ["dance_0005", "w_head_003"],    "red"),    # tay lớn + đầu giật
    (125.0, ["dance_0006", "w_head_004_v"],  "green"),
    (127.0, ["dance_0007", "w_head_011"],    "red"),
    (129.0, ["dance_0005", "w_head_012"],    "green"),
    (131.0, ["dance_0008", "w_head_003"],    "red"),
    (133.0, ["dance_0009", "w_head_004_v"],  "green"),
    (135.0, ["dance_0012", "w_head_013"],    "red"),
    (137.0, ["dance_0005", "w_head_014"],    "green"),
    (139.0, ["dance_0013", "w_head_003"],    "red"),
    (141.0, ["dance_0006", "w_head_004_v"],  "green"),
    (143.0, ["dance_0014", "w_head_015"],    "red"),
    (145.0, ["dance_0007", "w_head_016"],    "green"),
    (147.0, ["dance_0015", "w_head_017"],    "red"),
    (149.0, ["dance_0005", "w_head_011"],    "green"),
    (151.0, ["dance_0016", "w_head_012"],    "red"),
    (153.0, ["dance_0006", "w_head_013"],    "green"),
    (155.0, ["dance_0017", "w_head_003"],    "red"),
    (157.0, ["dance_0007", "w_head_004_v"],  "green"),
    (159.0, ["dance_0018", "w_head_014"],    "red"),
    (161.0, ["dance_0008", "w_head_015"],    "green"),
    (163.0, ["dance_0019", "w_head_016"],    "red"),    # max combo
    (165.0, ["dance_0005", "w_head_003"],    "green"),
    (167.0, ["dance_0020", "w_head_004_v"],  "red"),
    (169.0, ["dance_0006", "w_head_017"],    "green"),
    (171.0, ["dance_0021", "w_head_011"],    "red"),
    (173.0, ["dance_0007", "w_head_012"],    "green"),
    (175.0, ["dance_0022", "w_head_003"],    "red"),
    (177.0, ["dance_0005", "w_head_004_v"],  "green"),
    (179.0, ["dance_0023", "w_head_013"],    "red"),
    (181.5, ["dance_0006", "w_head_014"],    "green"),

    # ══ KẾT THÚC: robot shutdown ══════════════════════════════════════════════
    (184.0, "reboot_001",                    "white"),  # shutdown sequence
    (187.5, ["w_stand_001", "w_head_001"],   "white"),  # đứng thẳng, đầu cúi
    (191.0, "bow_avatar",                    "white"),  # cúi 45° — power off
]

# ── Lịch đèn theo section — độc lập với choreography ────────────────────────
# (start_t, end_t, [colors_cycle], pulse_interval_s)
_SECTION_LAMP_SCHEDULE: list[tuple[float, float, list, float]] = [
    (0.0,    15.0,  ["white"],                           2.0),   # INTRO: nhẹ nhàng
    (15.0,   35.0,  ["green"],                           1.5),   # VERSE 1: ổn định
    (35.0,   50.0,  ["green", "white"],                  0.8),   # PRE-CHORUS: tăng dần
    (50.0,   75.0,  ["red", "green", "white"],           0.4),   # CHORUS 1: ⚡ STROBE
    (75.0,   95.0,  ["green"],                           1.5),   # VERSE 2
    (95.0,   109.0, ["green", "white"],                  0.6),   # PRE-CHORUS 2
    (109.0,  123.0, ["white"],                           2.5),   # BRIDGE: chậm uy nghi
    (123.0,  184.0, ["red", "green", "white", "red"],    0.35),  # CHORUS FINAL: ⚡⚡ MAX
    (184.0,  195.0, ["white"],                           3.0),   # ENDING: tắt từ từ
]


async def _delete_file_later(path: Path, delay: int = 60):
    await asyncio.sleep(delay)
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


class RobotController:
    """
    Quản lý kết nối và điều khiển Alpha Mini.
    Nếu SDK không có, các method vẫn chạy nhưng không làm gì (no-op).
    """

    def __init__(self):
        self.device = None
        self.is_connected = False
        self._speech_observer = None
        # dùng để xoay vòng expression mắt khi nhảy/hành động
        self._expr_index = 0

    # ── Kết nối ───────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        if not SDK_AVAILABLE:
            log.warning("SDK not available — running in demo mode (no robot)")
            return False

        MiniSdk.set_log_level(logging.WARNING)
        MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)

        if ROBOT_IP:
            # Direct IP connection — faster, no mDNS needed
            log.info(f"🔌 Connecting directly to robot at {ROBOT_IP}:7000 …")
            self.device = WiFiDevice(
                name=ROBOT_SERIAL or "alphamini",
                address=ROBOT_IP,
                port=7000,
            )
        else:
            serial_display = ROBOT_SERIAL if ROBOT_SERIAL else "(any)"
            log.info(f"🔍 Searching for robot [{serial_display}] via mDNS…")
            self.device = await MiniSdk.get_device_by_name(ROBOT_SERIAL, timeout=15)
            if not self.device:
                log.error("❌ Robot not found. Ensure robot and server are on the same WiFi.")
                return False

        await MiniSdk.connect(self.device)
        await MiniSdk.enter_program()
        await asyncio.sleep(2)
        # Set volume tối đa
        await ChangeRobotVolume(volume=1.0).execute()
        log.info("Volume set to 100%")
        self.is_connected = True
        log.info(f"✅ Robot connected: {self.device}")
        return True

    async def disconnect(self):
        if SDK_AVAILABLE and self.is_connected:
            await MiniSdk.release()
        self.is_connected = False
        log.info("Robot disconnected")

    # ── TTS ───────────────────────────────────────────────────────────────────

    async def speak(self, text: str) -> bool:
        if not self._check_ready("speak"):
            return False
        try:
            # Dùng Edge TTS (Microsoft neural voice) — giống Xiaozhi, chất lượng cao
            # Hoạt động tốt ở VN, miễn phí, không cần API key
            import edge_tts
            filename = f"tts_{uuid.uuid4().hex[:8]}.mp3"
            mp3_path = TTS_DIR / filename
            tts = edge_tts.Communicate(text=text, voice="vi-VN-HoaiMyNeural")
            await tts.save(str(mp3_path))
            url = f"http://{SERVER_LOCAL_IP}:{SERVER_PORT}/audio/{filename}"
            log.info(f"TTS audio ready: {url}")
            (_, resp) = await PlayAudio(
                url=url,
                storage_type=AudioStorageType.NET_PUBLIC,
                volume=1.0,
            ).execute()
            log.info(f"PlayAudio result: {resp}")
            # Xóa file tạm sau 60s để tránh đầy disk
            asyncio.create_task(_delete_file_later(mp3_path, delay=60))
            return getattr(resp, "isSuccess", True)
        except Exception as e:
            log.error(f"speak error: {e}")
            return False

    async def stop_audio(self):
        if not self._check_ready("stop_audio"):
            return
        try:
            await StopAllAudio().execute()
        except Exception as e:
            log.error(f"stop_audio error: {e}")

    # ── Cảm xúc & Action ──────────────────────────────────────────────────────

    _LAMP_COLOR = {
        "green":  MouthLampColor.GREEN,
        "red":    MouthLampColor.RED,
        "blue":   MouthLampColor.WHITE,   # không có blue, dùng white
        "white":  MouthLampColor.WHITE,
        "yellow": MouthLampColor.GREEN,   # không có yellow, fallback green
    }
    _LAMP_MODE = {
        "normal":  MouthLampMode.NORMAL,
        "blink":   MouthLampMode.NORMAL,  # không có blink, dùng normal
        "breathe": MouthLampMode.BREATH,
    }

    # Ánh xạ emotion → expression mắt (codemaoX đã test OK trên robot)
    _EXPRESSION_BY_EMOTION = {
        "happy":     "codemao1",
        "sad":       "codemao2",
        "surprised": "codemao3",
        "thinking":  "codemao4",
        "dance":     "codemao5",
        "wave":      "codemao1",
    }

    # Pool expression cho các action / choreography không có emotion rõ ràng
    _EXPRESSION_DANCE_POOL = ["codemao1", "codemao2", "codemao3", "codemao4", "codemao5"]

    async def _play_auto_expression(self, emotion_hint: str | None = None):
        """
        Chọn một expression mắt phù hợp và phát song song với hành động cơ thể.
        Không raise lỗi nếu robot không hỗ trợ expression.
        """
        if not self._check_ready("_play_auto_expression"):
            return
        try:
            name = None
            if emotion_hint and emotion_hint in self._EXPRESSION_BY_EMOTION:
                name = self._EXPRESSION_BY_EMOTION[emotion_hint]
            else:
                pool = self._EXPRESSION_DANCE_POOL
                name = pool[self._expr_index % len(pool)]
                self._expr_index += 1

            if not name:
                return

            log.info(f"👀 Play eye expression: {name} (hint={emotion_hint})")
            await PlayExpression(express_name=name).execute()
        except Exception as e:
            # chỉ log cảnh báo, không làm hỏng luồng nhảy
            log.warning(f"_play_auto_expression error: {e}")

    async def perform_emotion(self, emotion: str):
        """
        Đèn miệng (ngay lập tức) + hành động robot tương ứng với emotion.
        Đèn và action chạy song song để phản hồi nhanh.
        """
        if not self._check_ready("perform_emotion"):
            return

        mapping = EMOTION_MAP.get(emotion, EMOTION_MAP["happy"])
        log.info(f"Emotion [{emotion}]: lamp={mapping.get('lamp')} action={mapping.get('action')}")

        # Đèn miệng + action + mắt chạy song song
        tasks = []

        color = self._LAMP_COLOR.get(mapping.get("lamp", "green"), MouthLampColor.GREEN)
        mode  = self._LAMP_MODE.get(mapping.get("lamp_mode", "normal"), MouthLampMode.NORMAL)
        tasks.append(SetMouthLamp(color=color, mode=mode, duration=8000).execute())

        if mapping.get("action"):
            tasks.append(PlayAction(action_name=mapping["action"]).execute())

        # mắt theo emotion (không fail toàn bộ nếu lỗi)
        tasks.append(self._play_auto_expression(emotion_hint=emotion))

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, r in enumerate(results):
                if isinstance(r, Exception):
                    log.warning(f"perform_emotion task[{i}] error: {r}")
                else:
                    log.info(f"perform_emotion task[{i}] ok: {r[1] if isinstance(r, tuple) else 'ok'}")
        except Exception as e:
            log.error(f"perform_emotion error: {e}")

    # ── Music + Dance ─────────────────────────────────────────────────────────

    async def play_music_with_dance(
        self,
        music_url: str,
        dance_ids: list[str] | None = None,
    ):
        """
        Phát nhạc từ URL và nhảy đồng thời.
        Robot tự dừng nhảy khi nhạc kết thúc.
        """
        if not self._check_ready("play_music_with_dance"):
            log.info(f"[DEMO] Would play music: {music_url}")
            return

        if dance_ids is None:
            dance_ids = [
                "dance_0001", "dance_0002", "dance_0003",
                "dance_0004", "dance_0005", "dance_0006",
            ]

        stop_event = asyncio.Event()

        async def _music():
            try:
                log.info(f"🎵 Playing music: {music_url}")
                await PlayAudio(
                    url=music_url,
                    storage_type=AudioStorageType.NET_PUBLIC,
                    volume=1.0,
                ).execute()
                log.info("🎵 Music finished")
            except Exception as e:
                log.error(f"Music error: {e}")
            finally:
                stop_event.set()

        async def _dance_loop():
            i = 0
            while not stop_event.is_set():
                dance_id = dance_ids[i % len(dance_ids)]
                log.info(f"💃 Dance step: {dance_id}")
                try:
                    # cơ thể + mắt nhảy cùng lúc
                    await asyncio.gather(
                        PlayAction(action_name=dance_id).execute(),
                        self._play_auto_expression(emotion_hint="dance"),
                        return_exceptions=True,
                    )
                except Exception as e:
                    log.warning(f"Dance step error ({dance_id}): {e}")
                    await asyncio.sleep(2)
                i += 1

        # Đèn nhấp nháy suốt lúc nhảy
        async def _lamp():
            colors = [MouthLampColor.GREEN, MouthLampColor.RED, MouthLampColor.WHITE]
            i = 0
            while not stop_event.is_set():
                await SetMouthLamp(
                    color=colors[i % len(colors)],
                    mode=MouthLampMode.BREATH,
                    duration=3000,
                ).execute()
                i += 1
                await asyncio.sleep(3)

        await asyncio.gather(_music(), _dance_loop(), _lamp(), return_exceptions=True)
        log.info("🎵 Music + dance finished")

    async def play_choreography_with_music(
        self,
        music_url: str,
        choreography: list[tuple[float, str, str]] | None = None,
    ) -> None:
        """
        Phát nhạc + thực hiện choreography đồng bộ theo timestamp chính xác.

        choreography: list of (timestamp_giây, action_id, màu_đèn)
        Mỗi action được trigger đúng lúc timestamp tương ứng trong bài nhạc.
        Nếu không truyền vào, mặc định dùng SEXY_LOVE_CHOREOGRAPHY.
        """
        if not self._check_ready("play_choreography_with_music"):
            log.info(f"[DEMO] Would play choreography with: {music_url}")
            return

        if choreography is None:
            choreography = SEXY_LOVE_CHOREOGRAPHY

        stop_event = asyncio.Event()
        start_time = asyncio.get_event_loop().time()

        async def _music():
            try:
                log.info(f"🎵 Choreo music start: {music_url}")
                await PlayAudio(
                    url=music_url,
                    storage_type=AudioStorageType.NET_PUBLIC,
                    volume=1.0,
                ).execute()
                log.info("🎵 Music finished")
            except Exception as e:
                log.error(f"Choreo music error: {e}")
            finally:
                stop_event.set()

        # ── Lamp driver theo section (độc lập với choreography) ──────────────
        async def _section_lamp_driver():
            """Điều khiển đèn theo section — strobe nhanh ở chorus, chậm ở bridge."""
            lamp_idx = 0
            schedule = _SECTION_LAMP_SCHEDULE
            while not stop_event.is_set():
                elapsed = asyncio.get_event_loop().time() - start_time
                # Tìm section hiện tại
                current = next(
                    ((colors, interval) for s, e, colors, interval in schedule
                     if s <= elapsed < e),
                    (["green"], 1.0),
                )
                colors, interval = current
                color_name = colors[lamp_idx % len(colors)]
                color = self._LAMP_COLOR.get(color_name, MouthLampColor.GREEN)
                asyncio.create_task(
                    SetMouthLamp(
                        color=color,
                        mode=MouthLampMode.BREATH,
                        duration=int(interval * 1000),
                    ).execute()
                )
                lamp_idx += 1
                try:
                    await asyncio.wait_for(
                        asyncio.shield(stop_event.wait()),
                        timeout=interval,
                    )
                    break
                except asyncio.TimeoutError:
                    pass

        # ── Filler: lấp khoảng trống > 1.8s bằng micro-movement ─────────────
        _FILLER = [
            "w_stand_001", "w_stand_003", "w_stand_005", "w_stand_007",
            "w_head_011",  "w_head_012",  "w_head_013",  "w_head_015",
        ]
        _fill_idx = 0

        async def _filler_loop():
            nonlocal _fill_idx
            while not stop_event.is_set():
                elapsed = asyncio.get_event_loop().time() - start_time
                gap = next(
                    (t - elapsed for t, _, _ in choreography if t > elapsed),
                    float("inf"),
                )
                if gap > 1.8:
                    fa = _FILLER[_fill_idx % len(_FILLER)]
                    _fill_idx += 1
                    asyncio.create_task(
                        PlayAction(action_name=fa, is_serial=False).execute()
                    )
                await asyncio.sleep(1.8)

        # ── Choreography runner — hỗ trợ multi-action combo ──────────────────
        async def _choreography_runner():
            for t, actions, _lamp_hint in choreography:
                elapsed = asyncio.get_event_loop().time() - start_time
                wait_time = t - elapsed

                if wait_time > 0:
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(stop_event.wait()),
                            timeout=wait_time,
                        )
                        log.info("🎵 Music ended, stopping choreography")
                        return
                    except asyncio.TimeoutError:
                        pass
                elif wait_time < -2.0:
                    log.debug(f"⏭ Skip late step t={t:.1f}s")
                    continue

                if stop_event.is_set():
                    return

                # Chuẩn hoá thành list
                action_list = [actions] if isinstance(actions, str) else actions
                combo_str = " + ".join(action_list)
                log.info(f"💃 Choreo t={t:.1f}s → [{combo_str}]")

                # Bắn tất cả actions song song (không chờ) + mắt dance
                for act in action_list:
                    asyncio.create_task(
                        PlayAction(action_name=act, is_serial=False).execute()
                    )
                asyncio.create_task(self._play_auto_expression(emotion_hint="dance"))

        await asyncio.gather(
            _music(),
            _choreography_runner(),
            _section_lamp_driver(),
            _filler_loop(),
            return_exceptions=True,
        )
        log.info("🎭 Choreography finished")

    async def play_action(self, action_id: str) -> bool:
        """Phát một action cụ thể theo ID (dùng khi bắt keyword trực tiếp)."""
        if not self._check_ready("play_action"):
            log.info(f"[DEMO] Would play action: {action_id}")
            return False
        try:
            log.info(f"▶ Playing action: {action_id}")
            # cơ thể + mắt đồng thời
            (_, resp) = await PlayAction(action_name=action_id).execute()
            asyncio.create_task(self._play_auto_expression(emotion_hint=None))
            ok = getattr(resp, "isSuccess", False)
            log.info(f"  Action '{action_id}': {'OK' if ok else 'FAIL'}")
            return ok
        except Exception as e:
            log.error(f"play_action error ({action_id}): {e}")
            return False

    async def speak_only(self, text: str) -> bool:
        """Chỉ phát TTS, không làm action/emotion (khi keyword action đang chạy)."""
        return await self.speak(text)

    # ── Nói + cảm xúc đồng thời ──────────────────────────────────────────────

    async def respond(self, text: str, emotion: str):
        """
        Nói TTS và thực hiện emotion animation song song.
        """
        if not self._check_ready("respond"):
            log.info(f"[DEMO] Robot would say: '{text}' with emotion: {emotion}")
            return
        await asyncio.gather(
            self.speak(text),
            self.perform_emotion(emotion),
            return_exceptions=True,
        )

    # ── Lắng nghe giọng nói ───────────────────────────────────────────────────

    async def start_listening(self, on_speech_detected):
        """
        Bật microphone robot, lắng nghe nhận diện giọng nói realtime.
        Khi phát hiện text → gọi callback on_speech_detected(text: str).
        """
        if not self._check_ready("start_listening"):
            return

        observer = ObserveSpeechRecognise()

        def _handler(msg: SpeechRecogniseResponse):
            if msg.isSuccess and msg.text and msg.text.strip():
                text = msg.text.strip()
                log.info(f"🎤 Robot heard: '{text}'")
                asyncio.create_task(on_speech_detected(text))

        observer.set_handler(_handler)
        observer.start()
        log.info("👂 Robot is now listening…")

    # ── Helper ────────────────────────────────────────────────────────────────

    def _check_ready(self, method: str) -> bool:
        if not SDK_AVAILABLE:
            log.debug(f"[DEMO] {method} called but SDK not available")
            return False
        if not self.is_connected:
            log.warning(f"{method} called but robot not connected")
            return False
        return True
