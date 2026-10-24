# Alpha Mini Server

## Cài môi trường server

Đã kiểm chứng trên Windows x64, PowerShell và Python 3.12. Môi trường đang dùng trước đợt này là Python 3.13.12; chưa kiểm thử lại toàn bộ trên Linux/macOS hay robot thật.

Từ thư mục gốc của bản clone, chạy lần lượt:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -r requirements.txt
```

`python` trong các lệnh trên phải trỏ tới Python 3.12. Không cần activate venv vì các lệnh dùng đường dẫn Python cụ thể. Requirements hiện vẫn dùng khoảng phiên bản cho các dependency đã có, nên không phải lockfile toàn bộ môi trường.

### SDK UBTECH

Requirements cài `alphamini==1.2.0` trực tiếp từ PyPI, không cần lấy wheel trong archive hoặc copy `site-packages` từ máy cũ. Đã kiểm chứng tải/cài bằng pip trong venv mới. Package này cung cấp module `mini`; các dependency của SDK được pip cài tự động.

Metadata của package ghi license GPLv3, nhưng file `alphamini-1.2.0.dist-info/LICENSE` đi kèm ghi MIT (Copyright 2020 UBTECH). Đây là sự khác biệt trong chính package; cần xác nhận với nhà cung cấp trước khi phân phối lại SDK. Repo này không đóng gói SDK vào vendor.

SDK có mã protobuf cũ. Phải đặt biến sau trong **mỗi cửa sổ PowerShell**, trước khi chạy Python/import server hoặc SDK:

```powershell
$env:PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION = 'python'
```

Nếu thiếu biến này, import SDK đã tái hiện lỗi `Descriptors cannot be created directly` với protobuf 5.29.6. Biến được đặt trước process, không chỉ thêm vào `.env`, vì một số import diễn ra trước khi server nạp `.env`.

### Cấu hình

Tạo `.env` local từ mẫu:

```powershell
Copy-Item .env.example .env
```

Điền cấu hình riêng trên máy: `GEMINI_API_KEY`; khi dùng robot, kiểm tra `ROBOT_ENABLED`, `ROBOT_IP`, `ROBOT_PORT`, `ROBOT_TYPE`, `ROBOT_AUTO_DISCOVER`. Cấu hình server gồm `SERVER_HOST`, `SERVER_PORT`, `ROBOT_AUDIO_PUBLIC_URL`. README không chứa giá trị key/token hoặc cấu hình robot riêng.

HTTPS dùng `SERVER_SSL_ENABLED`, `SERVER_SSL_CERTFILE`, `SERVER_SSL_KEYFILE`; chứng chỉ/khóa local nằm ở `ssl/server.crt` và `ssl/server.key`. Chúng không có trong bản clone. Không commit `.env` hoặc private key. Kiểm thử bên dưới dùng HTTP và tắt robot, không cần tạo chứng chỉ. Chưa kiểm chứng cấp chứng chỉ hoặc kết nối robot trong quy trình này.

### Kiểm tra local không gọi AI/robot

Các giá trị bên dưới chỉ phục vụ kiểm tra local; chuỗi API key là giá trị giả, không phải credential. Không dùng kết quả này để kết luận AI hay robot đã kết nối được.

```powershell
$env:GEMINI_API_KEY = 'offline-import-check-not-a-real-key'
$env:ROBOT_ENABLED = 'false'
$env:SERVER_SSL_ENABLED = 'false'
$env:SERVER_HOST = '127.0.0.1'
$env:SERVER_PORT = '18763'
.\.venv\Scripts\python.exe -B -c "import server"
.\.venv\Scripts\python.exe -B -c "import ws_mini_compat; from mini import mini_sdk; import cv2, numpy; from pyzbar.pyzbar import decode"
```

Để chạy cả kiểm tra app trong script verify, cần Node/npm và dependency app:

```powershell
Push-Location AlphaMiniApp
npm.cmd ci
Pop-Location
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1
```

`npm ci` phải áp dụng đủ ba patch hiện có. Verify chạy server import, TypeScript và Jest; pytest chạy 5 smoke test offline trong `tests/`. OpenCV dùng package headless vì server không cần GUI; QR được kiểm tra bằng import OpenCV, NumPy và pyzbar trên Windows.

### Khởi chạy

```powershell
.\.venv\Scripts\python.exe -B server.py
```

Với cấu hình kiểm thử trên, server đã trả HTTP 200 tại `http://127.0.0.1:18763/openapi.json`. Dừng bằng Ctrl+C. Khi chạy thật, mở cửa sổ PowerShell mới, đặt lại biến tương thích protobuf, điền `.env` bằng cấu hình riêng rồi chạy cùng lệnh; không giữ các biến kiểm thử giả. Các tích hợp AI, TTS bên ngoài, HTTPS và robot cần cấu hình/kiểm tra riêng.

### Offline server smoke tests

Install test dependencies into the same venv used for verification:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -B -m pytest -q tests
```

`requirements-dev.txt` adds only pytest; httpx is already installed by google-genai and is used by FastAPI TestClient. Tests set a fake API key, disable the robot and OpenClaw file bridge before importing the server, and exercise lifespan through TestClient. They do not call AI, TTS or an external network. QR images are generated in memory with OpenCV. Verify fails with installation instructions if pytest is missing.
