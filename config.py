import json
import os
import socket as _socket
from pathlib import Path

from dotenv import load_dotenv

# Luôn đọc .env cạnh package (không phụ thuộc cwd khi gọi uvicorn từ nơi khác).
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path, encoding="utf-8-sig")

def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# Gemini (AI Studio free tier: dùng Flash / Flash-Lite; lite tiết kiệm & RPM thường cao hơn)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

# STT (POST /voice/chat): model multimodal — flash-lite đôi khi hạn chế audio; mặc định ưu tiên flash đầy nếu lite.
_voice_stt = os.getenv("VOICE_STT_MODEL", "").strip()
if _voice_stt:
    VOICE_STT_MODEL = _voice_stt
else:
    VOICE_STT_MODEL = (
        "gemini-2.5-flash"
        if "lite" in GEMINI_MODEL.lower()
        else GEMINI_MODEL
    )
VOICE_MAX_UPLOAD_BYTES = int(os.getenv("VOICE_MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))
STT_TIMEOUT_SEC = float(os.getenv("STT_TIMEOUT_SEC", "45"))

# Robot Alpha Mini
ROBOT_IP      = os.getenv("ROBOT_IP", "192.168.1.100")
ROBOT_PORT    = int(os.getenv("ROBOT_PORT", "9090"))
ROBOT_ENABLED = _env_bool("ROBOT_ENABLED", default=False)
# Dòng robot theo SDK UBTECH: mini | edu | dedu | kor — phải khớp firmware (sai loại → WS/action lỗi).
ROBOT_TYPE = os.getenv("ROBOT_TYPE", "mini").strip().lower()
# True: khi kết nối, gọi mini_sdk.get_device_list (quét LAN) rồi ưu tiên IP tìm được — không cần đọc IP trên mắt robot; vẫn dùng ROBOT_IP trong .env làm dự phòng nếu quét trống.
ROBOT_AUTO_DISCOVER = _env_bool("ROBOT_AUTO_DISCOVER", default=True)
# Sau khi kết nối OK bằng IP vừa thử: ghi ROBOT_IP vào .env (UTF-8) để lần sau khởi động khớp mạng DHCP.
ROBOT_PERSIST_DISCOVERED_IP = _env_bool("ROBOT_PERSIST_DISCOVERED_IP", default=True)
ROBOT_DISCOVER_TIMEOUT_SEC = float(os.getenv("ROBOT_DISCOVER_TIMEOUT_SEC", "8"))
# Fallback khi mini_sdk.get_device_list trả rỗng: quét TCP trong subnet LAN hiện tại (vd 192.168.0.x).
ROBOT_DISCOVER_TCP_SWEEP = _env_bool("ROBOT_DISCOVER_TCP_SWEEP", default=True)
ROBOT_DISCOVER_TCP_TIMEOUT_SEC = float(os.getenv("ROBOT_DISCOVER_TCP_TIMEOUT_SEC", "0.22"))
ROBOT_DISCOVER_TCP_CONCURRENCY = int(os.getenv("ROBOT_DISCOVER_TCP_CONCURRENCY", "72"))
ROBOT_DISCOVER_TCP_MAX_HOSTS = int(os.getenv("ROBOT_DISCOVER_TCP_MAX_HOSTS", "254"))

# Tên behavior nhảy mặc định (SDK: StartBehavior). Nhạc = file âm gắn trong firmware của từng id — id khác nhau có/không nhạc.
# Xem GET /robot/behaviors (custom_actions). Lệnh nhảy có nhạc riêng + URL: dùng play_audio kèm URL hoặc mixi_show.
ROBOT_DEFAULT_BEHAVIOR = os.getenv("ROBOT_DEFAULT_BEHAVIOR", "dance_0004")
# Sau nhảy thành công, lần «nhảy» tiếp theo gọi StopAllAction rồi chờ (nhiều firmware bỏ qua StartBehavior nếu behavior cũ chưa dừng).
ROBOT_STOP_BEFORE_REPEAT_DANCE_SEC = float(os.getenv("ROBOT_STOP_BEFORE_REPEAT_DANCE_SEC", "0.2"))

# Tên inner action (SDK: PlayAction / mini_sdk.play_action). Để trống = thử danh sách mặc định.
ROBOT_SIT_ACTION = os.getenv("ROBOT_SIT_ACTION", "").strip()
ROBOT_STAND_ACTION = os.getenv("ROBOT_STAND_ACTION", "").strip()
# False: không thử mã "027" trong CSV ngồi (squat sâu / dễ ngã trên một số máy).
ROBOT_SIT_TRY_027 = _env_bool("ROBOT_SIT_TRY_027", default=True)
# Giống stand: thử PlayAction bằng mã số trước tên chữ — nhiều máy chỉ nhận số cho squat.
ROBOT_SIT_TRY_NUMERIC = _env_bool("ROBOT_SIT_TRY_NUMERIC", default=True)


def sit_numeric_fallback() -> list[str]:
    raw = os.getenv("ROBOT_SIT_NUMERIC_CSV", "027,026,025,024")
    ids = [x.strip() for x in raw.split(",") if x.strip()]
    if not ROBOT_SIT_TRY_027:
        ids = [x for x in ids if x not in ("027", "27")]
    return ids

# Giây chờ sau stop() trước khi gọi stand_up (áp dụng chung).
ROBOT_STAND_SETTLE_SEC = float(os.getenv("ROBOT_STAND_SETTLE_SEC", "0.75"))
# Sau khi execute_intent đã gọi stop() — chờ thêm trước stand_up (giảm motor sót / "chạy be").
ROBOT_STAND_AFTER_INTENT_STOP_SEC = float(os.getenv("ROBOT_STAND_AFTER_INTENT_STOP_SEC", "0.45"))
# Câu đứng rõ ràng (vd. chỉ «đứng»): không bỏ qua stand_up chỉ vì pose_state=standing (suy ra hay sai sau nhảy/đi).
ROBOT_STAND_IGNORE_POSE_WHEN_EXPLICIT = _env_bool("ROBOT_STAND_IGNORE_POSE_WHEN_EXPLICIT", default=True)
# Nếu đang từ tư thế "sitting" sang "standing": tăng settle để giảm giật/ngã.
ROBOT_STAND_FROM_SITTING_SETTLE_SEC = float(os.getenv("ROBOT_STAND_FROM_SITTING_SETTLE_SEC", "1.30"))
# Giữ thêm một chút sau khi đã chạy action đứng lên (best-effort) trước khi cho lệnh tiếp theo.
ROBOT_STAND_POST_STABILIZE_SEC = float(os.getenv("ROBOT_STAND_POST_STABILIZE_SEC", "0.35"))
# Khi đang từ tư thế "sitting" sang "standing": tránh thử một vài mã số dễ gây ngã.
# Ví dụ firmware nào đó map mã 028 sang động tác "cứng", dễ tụt lưng.
ROBOT_STAND_FROM_SITTING_AVOID_NUMERIC_CSV = os.getenv("ROBOT_STAND_FROM_SITTING_AVOID_NUMERIC_CSV", "028")

# Nếu phase 1 get_up thành công nhưng chưa ổn định đủ, thử thêm phase 2 để "lên hẳn" tư thế đứng.
ROBOT_STAND_FROM_SITTING_PHASE2_ENABLE = _env_bool(
    "ROBOT_STAND_FROM_SITTING_PHASE2_ENABLE", default=True
)
ROBOT_STAND_FROM_SITTING_PHASE2_SETTLE_SEC = float(
    os.getenv("ROBOT_STAND_FROM_SITTING_PHASE2_SETTLE_SEC", "0.20")
)
# Cuối danh stand: thử mã inner (tùy firmware; thường 028 sau khi 027 ngồi). Tắt: ROBOT_STAND_TRY_NUMERIC=false
ROBOT_STAND_TRY_NUMERIC = _env_bool("ROBOT_STAND_TRY_NUMERIC", default=True)
# Khi không suy ra "đang ngồi": thử mã số (028,…) *trước* chuỗi get_up/stand_up — nhiều máy chỉ nhận số.
ROBOT_STAND_NONSITTING_NUMERIC_BEFORE_NAMES = _env_bool(
    "ROBOT_STAND_NONSITTING_NUMERIC_BEFORE_NAMES", default=True
)
# stand_up RuntimeError → stop, chờ, reset pose, gọi stand_up lần 2.
ROBOT_STAND_RETRY_ON_FAIL = _env_bool("ROBOT_STAND_RETRY_ON_FAIL", default=True)

# Kết nối SDK tới ROBOT_IP (WebSocket) — thử lại khi mạng chập chờn.
ROBOT_CONNECT_RETRIES = int(os.getenv("ROBOT_CONNECT_RETRIES", "3"))
ROBOT_CONNECT_RETRY_DELAY_SEC = float(os.getenv("ROBOT_CONNECT_RETRY_DELAY_SEC", "2.5"))

# Sau take_picture_immediately(), SDK trả picPath trên robot — server thử tải ảnh qua HTTP.
# Thử lần lượt: ROBOT_IMAGE_URL_TEMPLATE (nếu có), rồi http://ROBOT_IP:PORT + path.
# Vi du template: http://{ip}:8080{path}
ROBOT_FILE_HTTP_PORTS = os.getenv("ROBOT_FILE_HTTP_PORTS", "8080,8888,80").strip()
ROBOT_IMAGE_URL_TEMPLATE = os.getenv("ROBOT_IMAGE_URL_TEMPLATE", "").strip()
# Lấy ảnh chụp: auto = thử bytes trong response SDK trước, rồi HTTP | sdk_only = chỉ bytes response | http_only = chỉ HTTP
_env_img_mode = os.getenv("ROBOT_IMAGE_FETCH_MODE", "auto").strip().lower()
ROBOT_IMAGE_FETCH_MODE = _env_img_mode if _env_img_mode in ("auto", "sdk_only", "http_only") else "auto"
# GET /robot/camera/frame — tối thiểu giữa hai lần chụp SDK (server còn floor 0.5s).
# Mặc định 1.25s: cân bằng cảm giác mượt và tải robot; giảm quá thấp dễ timeout/SDK lỗi.
ROBOT_CAMERA_POLL_MIN_SEC = float(os.getenv("ROBOT_CAMERA_POLL_MIN_SEC", "1.25"))
# take_picture code=-2: tự gọi enter_program() rồi chụp lại (một lần sau mỗi lần connect_robot thành công).
ROBOT_TAKE_PICTURE_RETRY_ENTER_PROGRAM = _env_bool("ROBOT_TAKE_PICTURE_RETRY_ENTER_PROGRAM", default=True)
# Nếu IMMEDIATELY vẫn lỗi: thử FINDFACE (cần có mặt trước camera).
ROBOT_TAKE_PICTURE_TRY_FINDFACE = _env_bool("ROBOT_TAKE_PICTURE_TRY_FINDFACE", default=False)


def stand_numeric_fallback() -> list[str]:
    raw = os.getenv("ROBOT_STAND_NUMERIC_CSV", "028,026,029,025,024")
    return [x.strip() for x in raw.split(",") if x.strip()]

# Giây chờ sau stop() trước khi gọi sit (thử tăng nếu firmware cần lâu hơn để thăng bằng).
ROBOT_SIT_STOP_SETTLE_SEC = float(os.getenv("ROBOT_SIT_STOP_SETTLE_SEC", "0.65"))

# JSON: {"bai1":"dance_0004","macarena":"dance_0005"} — key đã chuẩn hóa không dấu, viết thường
def _behavior_aliases() -> dict:
    raw = os.getenv("ROBOT_BEHAVIOR_ALIASES", "")
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


ROBOT_BEHAVIOR_ALIASES = _behavior_aliases()

# Behavior khi câu có cụm bài cụ thể (để trống = dùng ROBOT_DEFAULT_BEHAVIOR). Lấy id từ GET /robot/behaviors.
ROBOT_DANCE_NA_NA_BEHAVIOR = os.getenv("ROBOT_DANCE_NA_NA_BEHAVIOR", "").strip()
ROBOT_DANCE_MIXI_BEHAVIOR = os.getenv("ROBOT_DANCE_MIXI_BEHAVIOR", "").strip()
# «Múa võ» / kung fu — id StartBehavior trên firmware (vd. dance_0003). Để trống = cùng nhảy mặc định ROBOT_DEFAULT_BEHAVIOR.
ROBOT_MARTIAL_BEHAVIOR = os.getenv("ROBOT_MARTIAL_BEHAVIOR", "").strip()

# False = chỉ từ khóa (fix cứng, nhanh). True = thử Gemini khi không khớp keyword.
# True: khi keyword không khớp, gọi Gemini (llm_robot_intent) — tốn API; hữu ích câu tự nhiên dài.
ROBOT_SMART_INTENT = _env_bool("ROBOT_SMART_INTENT", default=False)

# Server
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
# HTTPS (uvicorn): truy cập từ thiết bị khác qua https://IP:port nếu cần (chứng chỉ dev: gen-dev-ssl.ps1).
# Có thể tắt nhanh bằng SERVER_SSL_ENABLED=false (hữu ích khi robot không tải được MP3 qua HTTPS self-signed).
SERVER_SSL_ENABLED = _env_bool("SERVER_SSL_ENABLED", default=True)
# Đặt file hoặc để mặc định ssl/server.crt + ssl/server.key (tạo bằng gen-dev-ssl.ps1).
_env_cert = os.getenv("SERVER_SSL_CERTFILE", "").strip()
_env_key = os.getenv("SERVER_SSL_KEYFILE", "").strip()
SERVER_SSL_CERTFILE = _env_cert
SERVER_SSL_KEYFILE = _env_key


# CORS: fetch từ OpenClaw Control UI (thường http://127.0.0.1:18789; có thể https nếu gateway bật TLS). Nhiều origin cách nhau bằng dấu phẩy; để trống = mặc định localhost OpenClaw (http + https).
CORS_ALLOW_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "").strip()


def server_ssl_cert_key() -> tuple[str, str] | None:
    """Trả (cert_path, key_path) nếu có chứng chỉ để bật HTTPS; không thì None."""
    if not SERVER_SSL_ENABLED:
        return None
    root = Path(__file__).resolve().parent

    def _resolve(p: str) -> Path:
        x = Path(p)
        return x if x.is_absolute() else (root / x)

    if _env_cert and _env_key:
        c, k = _resolve(_env_cert), _resolve(_env_key)
        if c.is_file() and k.is_file():
            return str(c.resolve()), str(k.resolve())
    dc, dk = root / "ssl" / "server.crt", root / "ssl" / "server.key"
    if dc.is_file() and dk.is_file():
        return str(dc.resolve()), str(dk.resolve())
    return None

# Sau khi có reply: robot phát TTS qua SDK (best-effort). Tắt nếu chỉ muốn STT / client tự đọc.
ROBOT_SPEAK_REPLIES = _env_bool("ROBOT_SPEAK_REPLIES", default=True)

# True: câu kiểu "đọc cho mình nghe" vẫn bật TTS dù client gửi speak=false (vd. OpenClaw).
ROBOT_SPEAK_FROM_PHRASES = _env_bool("ROBOT_SPEAK_FROM_PHRASES", default=True)

# Set volume trước khi phát TTS (giúp debug trường hợp robot gọi ok=True nhưng không nghe).
ROBOT_SET_VOLUME_BEFORE_TTS = _env_bool("ROBOT_SET_VOLUME_BEFORE_TTS", default=True)
ROBOT_TTS_VOLUME = float(os.getenv("ROBOT_TTS_VOLUME", "1.0"))
# Chống spam/lặp TTS cùng câu trong khoảng ngắn (giây).
ROBOT_TTS_DEDUP_SEC = float(os.getenv("ROBOT_TTS_DEDUP_SEC", "3.5"))

# Cách robot phát lời thoại:
#   sdk         — StartPlayTTS trước; nếu thất bại và có ROBOT_AUDIO_PUBLIC_URL thì tự fallback HTTP (MP3 + play_online_audio).
#   http_only   — chỉ MP3 (edge/fpt/google) rồi robot tải qua play_online_audio.
#   prefer_http — thử HTTP trước, lỗi thì SDK.
ROBOT_TTS_MODE = os.getenv("ROBOT_TTS_MODE", "sdk").strip().lower()
# Sau khi gọi play_online_audio(url), chờ tối đa N giây để server quan sát robot GET /robot/tts_media/<file>.
# 0 = bỏ kiểm tra fetch (hành vi cũ, có thể false-positive ok=True dù robot không phát).
ROBOT_TTS_FETCH_WAIT_SEC = float(os.getenv("ROBOT_TTS_FETCH_WAIT_SEC", "2.5"))

# URL gốc mà *robot* truy cập được tới máy chạy server (vd http://192.168.0.5:8000). Không dùng 127.0.0.1.
def detect_lan_ip() -> str:
    """
    Return the LAN IPv4 of this machine (same subnet as the robot).
    Uses UDP trick: connect to 8.8.8.8 without sending packets so
    the OS picks the correct outbound interface.
    Falls back to 127.0.0.1 if no network.
    """
    try:
        with _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM) as s:
            s.settimeout(0)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"

_audio_url_from_env = os.getenv("ROBOT_AUDIO_PUBLIC_URL", "").strip().rstrip("/")
if not _audio_url_from_env:
    _detected_ip = detect_lan_ip()
    _server_port = os.getenv("SERVER_PORT", "8000").strip()
    ROBOT_AUDIO_PUBLIC_URL = f"http://{_detected_ip}:{_server_port}"
else:
    ROBOT_AUDIO_PUBLIC_URL = _audio_url_from_env


def robot_audio_fetch_base_url() -> str:
    """
    URL de robot tai /robot/tts_media/... — dong bo scheme voi server:
    neu may chay HTTPS (ssl/server.crt) ma .env con http:// thi doi thanh https://
    (neu khong, robot fetch http vao cong chi co TLS -> play_online_audio that bai / im).
    """
    raw = (ROBOT_AUDIO_PUBLIC_URL or "").strip().rstrip("/")
    if not raw:
        return ""
    if raw.lower().startswith("http://") and server_ssl_cert_key() is not None:
        return "https://" + raw[7:]
    return raw


# FPT.AI Text-to-Speech v5 — https://docs.fpt.ai/docs/en/speech/api/text-to-speech/
# Đọc key trước để khi không set ROBOT_TTS_HTTP_ENGINE có thể mặc định fpt (giống console FPT).
FPT_AI_TTS_API_KEY = os.getenv("FPT_AI_TTS_API_KEY", "").strip()
FPT_AI_TTS_URL = os.getenv("FPT_AI_TTS_URL", "https://api.fpt.ai/hmi/tts/v5").strip().rstrip("/")
FPT_AI_TTS_VOICE = os.getenv("FPT_AI_TTS_VOICE", "minhquang").strip()
# Tốc độ -3 … +3 (0 = bình thường)
FPT_AI_TTS_SPEED = os.getenv("FPT_AI_TTS_SPEED", "0").strip()
FPT_AI_TTS_FORMAT = os.getenv("FPT_AI_TTS_FORMAT", "mp3").strip().lower()
# Console FPT thường dùng "api-key"; doc mẫu cũ dùng "api_key"
FPT_AI_TTS_API_HEADER = os.getenv("FPT_AI_TTS_API_HEADER", "api-key").strip()
FPT_AI_TTS_POLL_TIMEOUT_SEC = float(os.getenv("FPT_AI_TTS_POLL_TIMEOUT_SEC", "120"))

# Engine cho http_only/prefer_http:
#   edge  — không cần key
#   fpt   — FPT.AI v5 (voice/speed như console; cần FPT_AI_TTS_API_KEY)
#   google — GOOGLE_APPLICATION_CREDENTIALS + pip google-cloud-texttospeech
# Không set ROBOT_TTS_HTTP_ENGINE → fpt nếu đã có FPT_AI_TTS_API_KEY, không thì edge.
_tts_http_engine_env = os.getenv("ROBOT_TTS_HTTP_ENGINE", "").strip().lower()
ROBOT_TTS_HTTP_ENGINE = _tts_http_engine_env or ("fpt" if FPT_AI_TTS_API_KEY else "edge")
# Edge: vi-VN-HoaiMyNeural (nữ), vi-VN-NamMinhNeural (nam) — chỉ 2 giọng neural tiếng Việt.
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "vi-VN-HoaiMyNeural")
# Tốc độ/âm lượng/cao độ Edge (pitch cao hơn +Hz → gần “trẻ” hơn với giọng nam NamMinh; Edge chỉ có 2 giọng VN).
EDGE_TTS_RATE = os.getenv("EDGE_TTS_RATE", "-10%").strip()
EDGE_TTS_PITCH = os.getenv("EDGE_TTS_PITCH", "+0Hz").strip()
EDGE_TTS_VOLUME = os.getenv("EDGE_TTS_VOLUME", "+0%").strip()
GOOGLE_TTS_LANGUAGE_CODE = os.getenv("GOOGLE_TTS_LANGUAGE_CODE", "vi-VN")
# Để trống → API chọn mặc định. Khuyến nghị khi muốn giọng tự nhiên hơn Edge: vi-VN-Neural2-A (Google Cloud).
GOOGLE_TTS_VOICE_NAME = os.getenv("GOOGLE_TTS_VOICE_NAME", "").strip()
GOOGLE_TTS_SPEAKING_RATE = float(os.getenv("GOOGLE_TTS_SPEAKING_RATE", "1.0"))

# System prompt
SYSTEM_PROMPT = "Ban la Alpha Mini - mot robot AI than thien, de thuong va thong minh. Ban dang tro chuyen voi nguoi dung qua ung dung nhan tin. Tra loi ngan gon, tu nhien bang tieng Viet. Khi nguoi dung yeu cau hanh dong (nhay, chao, di...), hay xac nhan va mo ta hanh dong ban dang thuc hien."

# ── OpenClaw file bridge (không dùng exec) ────────────────────────────────
# OpenClaw hiện tại đang lỗi phần `exec` (unsupported platform), nên ta chuyển sang:
# - Skill OpenClaw dùng tool `write` để ghi nội dung chat vào file này
# - Backend server tự polling file và điều khiển robot
OPENCLAW_FILE_BRIDGE_ENABLED = _env_bool("OPENCLAW_FILE_BRIDGE_ENABLED", default=True)
OPENCLAW_FILE_BRIDGE_POLL_SEC = float(os.getenv("OPENCLAW_FILE_BRIDGE_POLL_SEC", "0.4"))
OPENCLAW_FILE_BRIDGE_DEBOUNCE_READS = int(os.getenv("OPENCLAW_FILE_BRIDGE_DEBOUNCE_READS", "2"))
OPENCLAW_FILE_BRIDGE_CLEAR_AFTER = _env_bool("OPENCLAW_FILE_BRIDGE_CLEAR_AFTER", default=True)
OPENCLAW_FILE_BRIDGE_SPEAK = _env_bool("OPENCLAW_FILE_BRIDGE_SPEAK", default=True)

# Mặc định: ~/.openclaw/workspace/.alphamini_pending_chat.txt
OPENCLAW_PENDING_CHAT_PATH = os.getenv(
    "OPENCLAW_PENDING_CHAT_PATH",
    os.path.join(os.path.expanduser("~"), ".openclaw", "workspace", ".alphamini_pending_chat.txt"),
).strip()

# Cùng thư mục workspace OpenClaw — phản hồi chat cho agent đọc lại.
_openclaw_ws = os.path.dirname(os.path.abspath(OPENCLAW_PENDING_CHAT_PATH))
OPENCLAW_LAST_REPLY_PATH = os.getenv(
    "OPENCLAW_LAST_REPLY_PATH",
    os.path.join(_openclaw_ws, ".alphamini_last_reply.txt"),
).strip()
