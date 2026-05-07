# Alpha Mini AI Chatbot — Setup Guide

## Kiểm tra code vs SDK chính thức của UBTech

### ✅ So sánh API calls — Code của chúng ta vs Official alphamini SDK

| Chức năng | Official SDK | Code của chúng ta | Trạng thái |
|---|---|---|---|
| Khởi tạo SDK | `MiniSdk.set_robot_type(MiniSdk.RobotType.EDU)` | ✅ Giống | ✅ Đúng |
| Tìm robot | `MiniSdk.get_device_by_name(serial, timeout=15)` | ✅ Giống | ✅ Đúng |
| Kết nối | `MiniSdk.connect(device)` | ✅ Giống | ✅ Đúng |
| Bắt đầu chương trình | `StartRunProgram().execute()` | ✅ Giống | ✅ Đúng |
| TTS nói | `StartPlayTTS(text=text).execute()` | ✅ Giống | ✅ Đúng |
| Thực hiện action | `PlayAction(action_name=name).execute()` | ✅ Giống | ✅ Đúng |
| Biểu cảm mặt | `PlayExpression(address_name=name).execute()` | ✅ Giống | ✅ Đúng |
| Đèn miệng | `SetMouthLamp(color, mode, duration).execute()` | ✅ Giống | ✅ Đúng |
| Lắng nghe giọng nói | `ObserveSpeechRecognise()` + `.set_handler()` + `.start()` | ✅ Giống | ✅ Đúng |
| Nhận diện mặt | `FaceDetect(timeout).execute()` | ✅ Giống | ✅ Đúng |
| Di chuyển | `MoveRobot(step, direction).execute()` | ✅ Giống | ✅ Đúng |
| Ngắt kết nối | `MiniSdk.release()` | ✅ Giống | ✅ Đúng |

### ✅ Tên action hợp lệ (từ tài liệu hãng + oversea SDK)

| Tên trong code | Ý nghĩa | Nguồn |
|---|---|---|
| `"018"` | Vẫy tay | alphamini Python SDK scene file |
| `"say_hi"` | Chào hỏi | call-builtin-skills.txt |
| `"dancing"` | Nhảy múa | call-builtin-skills.txt |
| `"dance_0001en"` | Điệu nhảy 1 (bản Oversea) | alphamini Python SDK |
| `"dance_0002en"` | Điệu nhảy 2 (bản Oversea) | alphamini Python SDK |
| `"sit_down"` | Ngồi xuống | call-builtin-skills.txt |
| `"stand_up"` | Đứng lên | call-builtin-skills.txt |
| `"nod"` | Gật đầu | call-builtin-skills.txt |
| `"shake_head"` | Lắc đầu | call-builtin-skills.txt |
| `"be_cute"` | Làm nũng | call-builtin-skills.txt |
| `"greeting"` | Chào | alphamini Python SDK |

---

## Hướng Dẫn Setup Từng Bước

---

## BƯỚC 1 — Cài Python (nếu chưa có)

1. Tải Python tại: https://python.org/downloads
2. Tick **"Add Python to PATH"** khi cài
3. Kiểm tra:
```cmd
python --version   → Python 3.10+ 
pip --version      → pip 23+
```

---

## BƯỚC 2 — Lấy Groq API Key (miễn phí)

1. Vào: **https://console.groq.com/keys**
2. Đăng nhập bằng Google (30 giây, không cần thẻ)
3. Nhấn **"Create API Key"**
4. Copy key bắt đầu bằng `gsk_...`
5. Điền vào `config.py`:

```python
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "gsk_YOUR_KEY_HERE")
```

> **Groq free tier:** 14.400 req/ngày, 30 req/phút, model Llama 3.3 70B

---

## BƯỚC 3 — Cài dependencies Python

Mở terminal, chạy:

```bash
cd "d:\User\Downloads\UBtech docs\UBtech docs\AlphaMiniServer"
pip install -r requirements.txt
```

Hoặc **double-click** `start_server.bat` (tự động cài).

---

## BƯỚC 4 — Cấu hình Robot

### 4.1. Bật robot và kết nối WiFi

1. Bật robot Alpha Mini
2. Nói: **"Hi Mini, connect WiFi"** hoặc dùng app chính thức để kết nối WiFi
3. Robot và PC phải **cùng mạng WiFi LAN**

### 4.2. Tìm serial number robot (tùy chọn)

- In ở mặt lưng robot: VD `00018`, `FC001`, v.v.
- Điền vào `config.py`:
```python
ROBOT_SERIAL = ""   # "" = tìm bất kỳ robot nào trên mạng
```

### 4.3. Yêu cầu mạng

```
[PC chạy Server] ──── WiFi LAN ──── [Robot Alpha Mini]
[Điện thoại]    ──── WiFi LAN ──── [PC chạy Server]
```
> ⚠️ Tất cả phải cùng 1 mạng WiFi. Không dùng được qua mobile data.

---

## BƯỚC 5 — Chạy Bridge Server

```bash
# Cách 1: double-click
start_server.bat

# Cách 2: terminal
cd "d:\User\Downloads\UBtech docs\UBtech docs\AlphaMiniServer"
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

**Kết quả thành công:**
```
✅ Groq [llama-3.3-70b-versatile] sẵn sàng (FREE - 14400 req/ngày)
🔍 Searching for robot []…
✅ Robot connected: WiFiDevice(...)
🤖 Robot: "Xin chào! Tôi là Alpha Mini..."
👂 Robot is now listening…
INFO: Uvicorn running on http://0.0.0.0:8000
```

**Xem IP của máy** (sẽ in ra khi chạy `start_server.bat`):
```
>>> 192.168.1.100   ← Ghi IP này lại, dùng cho Flutter app
```

---

## BƯỚC 6 — Build và cài Flutter App

### 6.1. Cài Flutter SDK

1. Tải: https://flutter.dev/docs/get-started/install/windows
2. Giải nén vào `C:\flutter`
3. Thêm `C:\flutter\bin` vào PATH
4. Kiểm tra:
```bash
flutter doctor   → phải xanh hết (hoặc chỉ thiếu Chrome là OK)
```

### 6.2. Build APK

```bash
cd "d:\User\Downloads\UBtech docs\UBtech docs\AlphaMiniFlutter\alphamini_controller"
flutter pub get
flutter build apk --release
```

APK tại: `build/app/outputs/flutter-apk/app-release.apk`

### 6.3. Cài APK lên điện thoại

```bash
# Cách 1: ADB (điện thoại kết nối USB)
adb install build/app/outputs/flutter-apk/app-release.apk

# Cách 2: Copy APK → gửi qua Telegram → tải về điện thoại → cài
```

---

## BƯỚC 7 — Sử dụng

1. Mở app **AlphaMini Controller** trên điện thoại
2. Nhập IP server (VD: `192.168.1.100`)
3. Nhấn **"Chat AI"**
4. Bắt đầu nhắn tin hoặc nói chuyện với robot!

---

## Xiaozhi Android (SelfHost)

App Xiaozhi có thể kết nối tới Alpha Mini Server:

1. Chọn **SelfHost** trong app Xiaozhi
2. WebSocket URL: `ws://IP_SERVER:8000/ws/xiaozhi`  
   (VD: `ws://192.168.1.100:8000/ws/xiaozhi`)
3. Nhấn **连接** (Kết nối)

**Yêu cầu thêm:**
- **ffmpeg** trong PATH (decode Opus cho ASR)
- **OPENAI_API_KEY** trong config.py (Whisper ASR — nhận dạng giọng nói)

Nếu chưa cấu hình OPENAI_API_KEY, app vẫn kết nối được nhưng giọng nói sẽ không nhận diện.

---

## Cấu trúc Files Server

```
AlphaMiniServer/
├── config.py           ← ✏️ Sửa ở đây: API keys, robot serial
├── ai_service.py       ← LLM: Groq/Gemini/OpenAI + memory
├── robot_controller.py ← alphamini SDK wrapper
├── server.py           ← FastAPI + WebSocket
├── requirements.txt    ← Dependencies
├── start_server.bat    ← Double-click để chạy
└── logs/
    └── server.log      ← Log file
```

---

## Troubleshooting

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| `Robot not found` | Robot chưa kết nối WiFi hoặc khác mạng | Kết nối robot cùng WiFi với PC |
| `Groq API error` | Key chưa điền | Điền `GROQ_API_KEY` trong config.py |
| `WebSocket connection refused` | Server chưa chạy | Chạy `start_server.bat` |
| `App can't connect` | Sai IP | Chạy `ipconfig` để lấy IP đúng |
| `TTS không hoạt động` | Robot chưa StartRunProgram | Chờ 4 giây sau khi kết nối |
| `alphamini not found` | Chưa cài package | `pip install alphamini` |

---

## Test nhanh không cần robot

Server hoạt động ở **"demo mode"** nếu không tìm thấy robot.
AI vẫn chat bình thường, chỉ không có robot thực hiện hành động.

Test AI qua REST API:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"Xin chào! Bạn tên gì?\"}"
```

Hoặc mở: **http://localhost:8000/docs** (Swagger UI)
