"""
config.py — Cấu hình trung tâm cho Alpha Mini AI Chatbot Server
Sửa các giá trị ở đây, không cần đụng vào code logic.
"""
import os

# ── Chọn LLM provider ─────────────────────────────────────────────────────────
# "groq"    → Groq (MIỄN PHÍ, 14400 req/ngày, NHANH NHẤT) ← KHUYẾN NGHỊ
# "gemini"  → Google Gemini (miễn phí, 1500 req/ngày)
# "openai"  → OpenAI GPT-4o-mini (trả phí)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")

# ── API Keys (chỉ qua biến môi trường / file .env — không hardcode lên git) ───
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Groq — lấy key miễn phí tại: console.groq.com/keys
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")

# ── Robot ─────────────────────────────────────────────────────────────────────
# Serial number in ở lưng robot (4-5 ký tự cuối), hoặc "" để tìm bất kỳ robot
ROBOT_SERIAL = os.getenv("ROBOT_SERIAL", "010058YUD18112108284")
# IP trực tiếp của robot (bỏ qua mDNS scan, nhanh hơn) — "" để dùng mDNS
# Hiện tại robot đang ở mạng hotspot Tab S8: 10.47.218.163
ROBOT_IP = os.getenv("ROBOT_IP", "10.47.218.163")

# ── Server ────────────────────────────────────────────────────────────────────
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000
# IP của máy tính server (để robot download file TTS qua WiFi)
# PC hiện tại trên mạng Tab S8: 10.47.218.130
SERVER_LOCAL_IP = os.getenv("SERVER_LOCAL_IP", "10.47.218.130")

# ── Giữ bao nhiêu turn trong conversation history ────────────────────────────
MAX_HISTORY_TURNS = 20   # 20 turn = 40 messages (user + bot)

# ── System prompt — định nghĩa tính cách robot ───────────────────────────────
SYSTEM_PROMPT = """
Bạn là Alpha Mini — một robot humanoid nhỏ nhắn, thông minh và rất thân thiện.
Bạn trò chuyện tự nhiên, ngắn gọn (tối đa 2-3 câu mỗi lượt), dễ hiểu với mọi lứa tuổi.
Bạn luôn nhiệt tình, lạc quan và hay đặt câu hỏi ngược lại để duy trì cuộc trò chuyện.
Hãy trả lời bằng tiếng Việt trừ khi người dùng nói tiếng khác.

QUAN TRỌNG — Tags bắt buộc ở CUỐI mỗi câu trả lời:

1. EMOTION tag (bắt buộc):
[EMOTION:happy|sad|surprised|thinking|dance|wave]

2. ACTION tag (tùy chọn — chỉ thêm khi người dùng yêu cầu hành động thể chất):
[ACTION:nhảy|vẫy tay|cúi chào|bắt tay|ôm|đứng dậy|ngồi|rap|thăng bằng|chụp ảnh]

Ví dụ:
- "Xin chào! Rất vui được gặp bạn! [EMOTION:happy]"
- "Nhảy nào! Một... hai... ba! [EMOTION:dance][ACTION:nhảy]"
- "Ồ thật thú vị! Kể thêm đi! [EMOTION:surprised]"
- "Để tôi cúi chào bạn nhé! [EMOTION:wave][ACTION:cúi chào]"
- "Tôi đang suy nghĩ... [EMOTION:thinking]"
- "Tôi buồn quá. [EMOTION:sad]"
"""

# ── Keyword → action trực tiếp (bắt động từ trong câu người dùng / AI) ───────
# Key: chuỗi con cần có trong text (viết thường, không dấu cũng khớp)
# Value: action ID từ GetActionList() đã xác nhận
KEYWORD_ACTION_MAP = {
    # Nhảy múa
    "nhay":         "dance_0001",
    "nhảy":         "dance_0001",
    "nhảy múa":     "dance_0002",
    "múa":          "dance_0003",
    "dance":        "dance_0001",
    # Chào hỏi
    "vẫy tay":      "say_hello_avatar",
    "vay tay":      "say_hello_avatar",
    "xin chào":     "say_hello_avatar",
    "chào":         "w_hello_101a",
    "hello":        "w_hello_201a",
    "hi ":          "w_hello_101a",
    # Cúi chào
    "cúi chào":     "bow_avatar",
    "cui chao":     "bow_avatar",
    "bow":          "bow_avatar",
    # Bắt tay
    "bắt tay":      "handshake_avatar",
    "bat tay":      "handshake_avatar",
    "handshake":    "handshake_avatar",
    # Ôm
    "ôm":           "hug_avatar",
    "om ban":       "hug_avatar",
    "hug":          "hug_avatar",
    # Đứng dậy
    "đứng dậy":     "stand_up",
    "dung day":     "stand_up",
    "stand up":     "stand_up",
    # Ngồi xuống
    "ngồi xuống":   "standbysquat_001",
    "ngoi xuong":   "standbysquat_001",
    "ngồi":         "standbysquat_001",
    "sit down":     "standbysquat_001",
    # Hôn gió
    "hôn gió":      "air_kiss_avatar",
    "hon gio":      "air_kiss_avatar",
    "kiss":         "air_kiss_avatar",
    # Chụp ảnh
    "chụp ảnh":     "photograph_001",
    "chup anh":     "photograph_001",
    "selfie":       "photograph_001",
    # Giữ thăng bằng / yoga
    "thăng bằng":   "balance",
    "thang bang":   "balance",
    "balance":      "balance",
    # Tập thể dục / vận động ngẫu nhiên
    "vận động":     "random_short1",
    "van dong":     "random_short1",
    "làm gì đó":    "random_short2",
    "ngẫu nhiên":   "random_short3",
    # Biểu diễn rap
    "rap":          "rap",
    # Giơ tay / chỉ đường
    "giơ tay":      "w_head_001",
    "gio tay":      "w_head_001",
    # Ngủ
    "ngủ đi":       "sleepmode_001",
    "ngu":          "sleepmode_001",
    "sleep":        "sleepmode_001",
}

# ── Tên bài hát trigger play_music (xử lý riêng trong server.py) ─────────────
# Key: keyword trong câu chat, Value: tên bài để lookup SONG_PRESETS
MUSIC_KEYWORD_MAP = {
    "sexy love":          "sexy love",
    "t-ara":              "sexy love",
    "t ara":              "sexy love",
    "bopeep":             "bopeep",
    "bo peep":            "bopeep",
    "lovey dovey":        "lovey dovey",
    "gangnam":            "gangnam style",
    "sorry sorry":        "sorry sorry",
    # Jiafei - Ye Hua Xiang (野花香)
    "jiafei":             "jiafei ye hua xiang",
    "ye hua xiang":       "jiafei ye hua xiang",
    "jiafei ye hua":      "jiafei ye hua xiang",
    "jiafei ye hua xiang":"jiafei ye hua xiang",
    # Bài Tết sôi động (YouTube id gU3lD2rNA9s)
    "chúc tết":           "tet_chuc_tet",
    "chuc tet":           "tet_chuc_tet",
    "nhảy chúc tết":      "tet_chuc_tet",
    "nhay chuc tet":      "tet_chuc_tet",
}

# ── Mapping emotion → robot action ───────────────────────────────────────────
# action IDs đã xác nhận từ GetActionList() trên robot thực tế
EMOTION_MAP = {
    "happy":     {"lamp": "green",  "lamp_mode": "breathe", "action": "speakingAct1"},
    "sad":       {"lamp": "red",    "lamp_mode": "normal",  "action": "021"},
    "surprised": {"lamp": "green",  "lamp_mode": "normal",  "action": "017"},
    "thinking":  {"lamp": "white",  "lamp_mode": "breathe", "action": "random_short1"},
    "dance":     {"lamp": "green",  "lamp_mode": "breathe", "action": "dance_0001"},
    "wave":      {"lamp": "green",  "lamp_mode": "normal",  "action": "say_hello_avatar"},
}
