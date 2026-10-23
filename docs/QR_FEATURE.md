# QR scan — Alpha Mini

## Endpoint

| Path | Method | Mục đích |
|------|--------|---------|
| `GET /qr/scan` | GET | Trang web 3 tab: webcam PC, camera robot, upload |
| `POST /qr/decode` | POST multipart `file=` | Decode QR từ ảnh upload |
| `POST /qr/decode_base64` | POST JSON `{image_b64}` | Decode từ base64 (cho browser canvas) |
| `POST /robot/qr/from_camera` | POST `?auto_chat=true\|false` | Chụp camera robot → decode |
| `POST /chat/qr-scan` | POST `?auto_chat=true\|false` | Alias cũ của `/robot/qr/from_camera` (giữ tương thích) |
| `GET /qr/history?limit=50` | GET | Liệt kê lịch sử |
| `DELETE /qr/history` | DELETE | Xoá lịch sử |

## Hành vi mặc định

Khi quét được QR:

1. Lưu vào `qr_history.jsonl` (JSONL persistent log).
2. Dedupe: cùng `text` trong `QR_DEDUPE_WINDOW_SEC` giây (mặc định 4s) bị bỏ qua.
3. **Nếu `QR_AUTO_CHAT=true`** (default): đẩy `"QR Code: <text>"` vào Gemini chat → reply hiển thị + robot đọc to nếu `ROBOT_SPEAK_REPLIES=true`.
4. **Nếu `QR_AUTO_CHAT=false`**: chỉ trả JSON thô; robot tự đọc nội dung QR nếu `QR_ROBOT_SPEAK_RAW=true`.

## Intent từ chat

User gõ "quét qr giúp mình" / "scan qr" / "đọc mã QR" trong `/chat` → server tự kích hoạt scan flow → trả reply trong cùng turn.

## Cấu hình `.env`

```
QR_AUTO_CHAT=true
QR_HISTORY_PATH=qr_history.jsonl
QR_DEDUPE_WINDOW_SEC=4.0
QR_HISTORY_MAX_IN_MEMORY=200
QR_ROBOT_SPEAK_RAW=true
```

## Cài đặt phụ thuộc

```bash
pip install opencv-python pyzbar numpy
# Linux: sudo apt install libzbar0
# macOS: brew install zbar
# Windows: pyzbar wheel có sẵn DLL
```

## Decoder

`qr_module.decode_qr_codes()` thử pyzbar trước (chính xác cao trên QR nghiêng/mờ),
fallback `cv2.QRCodeDetector` nếu pyzbar miss. Cả hai vắng → trả `[]` + log warning.
