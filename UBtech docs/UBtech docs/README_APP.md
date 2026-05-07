# Alpha Mini Voice App — Hướng dẫn tích hợp

Ứng dụng Android tích hợp **UDP Discovery**, **WebSocket Chat**, **Voice Input** và **Robot Control** với Alpha Mini Server.

## Cấu trúc dự án

```
UBtech docs/
├── AlphaMiniServer/          # Python FastAPI server (AI + Robot)
├── AlphaMiniVoiceApp/        # App Android mới — tích hợp tất cả
├── Xiaozhi_Android-main/     # Xiaozhi SelfHost (ws://IP:8000/ws/xiaozhi)
├── source code/SpeechDemoFramework/  # Chạy trên robot (WeiNa, TencentVad)
└── Extra/
    ├── AlphaMiniDiscovery/   # SDK robot (gesture, action)
    ├── mini-outer-sdk-demo/   # Điều khiển robot qua SDK
    └── Oversea-SpeechServiceDemo/
```

## AlphaMiniVoiceApp — App tích hợp

### Tính năng
- **UDP Discovery**: Tự tìm Alpha Mini Server trong mạng LAN (broadcast port 54545)
- **WebSocket Chat**: Kết nối `ws://IP:8000/ws/chat`
- **Voice Input**: Android SpeechRecognizer (tiếng Việt)
- **Robot Control**: Reset, Vẫy tay, Nhảy, Dừng nhạc

### Cách sử dụng

1. **Chạy Alpha Mini Server** (PC/điện thoại cùng WiFi):
   ```bash
   cd AlphaMiniServer
   python -m uvicorn server:app --host 0.0.0.0 --port 8000
   ```

2. **Mở app Alpha Mini Voice** trên điện thoại

3. **Tìm server**: Nhấn "🔍 Tìm server" — app gửi UDP broadcast, server trả IP + port

4. **Kết nối**: Nhấn "Kết nối" (hoặc nhập IP thủ công nếu discovery không hoạt động)

5. **Trò chuyện**:
   - Gõ text + nhấn Gửi
   - Hoặc nhấn 🎤 Nói → nói → text tự điền và gửi

6. **Điều khiển robot**: Reset, 👋 Vẫy, 💃 Nhảy, ⏹ Dừng

### Build app

1. Đảm bảo đã cài **Android SDK** và set `ANDROID_HOME` hoặc tạo `local.properties`:
   ```
   sdk.dir=C:\\Users\\YourName\\AppData\\Local\\Android\\Sdk
   ```

2. Build:
   ```bash
   cd "UBtech docs/AlphaMiniVoiceApp"
   gradlew.bat assembleDebug   # Windows
   ./gradlew assembleDebug     # Linux/Mac
   ```
   APK: `app/build/outputs/apk/debug/app-debug.apk`

## Xiaozhi SelfHost (giọng nói end-to-end)

Xiaozhi Android hỗ trợ SelfHost với giao thức Opus/WebSocket:

1. Cài Xiaozhi Android
2. Chọn **SelfHost** → nhập `ws://IP_SERVER:8000/ws/xiaozhi`
3. Server cần: `ffmpeg`, `OPENAI_API_KEY` (Whisper ASR), `edge-tts`, `pydub`

## Luồng tích hợp

```
[Điện thoại]                    [Alpha Mini Server]              [Robot]
     │                                   │                          │
     │  UDP "ALPHAMINI_DISCOVER"         │                          │
     │ ────────────────────────────────> │                          │
     │  JSON {ip, port}                  │                          │
     │ <──────────────────────────────── │                          │
     │                                   │                          │
     │  WebSocket /ws/chat               │                          │
     │ ────────────────────────────────> │                          │
     │  {"type":"chat","text":"..."}     │  AI (Groq/Gemini)        │
     │                                   │ ──> TTS + Action ───────> │
     │  {"type":"conversation",...}       │                          │
     │ <──────────────────────────────── │                          │
```

## Cấu hình

- **config.py**: `ROBOT_IP`, `SERVER_LOCAL_IP`, `GROQ_API_KEY`, `OPENAI_API_KEY` (cho Xiaozhi)
- **App mặc định**: IP `10.47.218.130`, port `8000` — sửa trong `activity_main.xml` hoặc dùng Discovery
