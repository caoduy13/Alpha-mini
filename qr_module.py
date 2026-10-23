"""
Alpha Mini — module QR scan (decode + history + dedupe).
Tách khỏi server.py để dễ test và bảo trì. Phụ thuộc: opencv-python, pyzbar (libzbar), numpy.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


def _probe_pyzbar() -> bool:
    try:
        import pyzbar.pyzbar  # noqa: F401
        return True
    except Exception as e:
        log.info("pyzbar unavailable (%s) — fallback cv2.QRCodeDetector", e)
        return False


def _probe_cv2() -> bool:
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        return True
    except Exception as e:
        log.warning("cv2/numpy unavailable: %s", e)
        return False


_PYZBAR_OK = _probe_pyzbar()
_CV2_OK = _probe_cv2()
QR_DECODER_AVAILABLE: tuple[bool, bool] = (_PYZBAR_OK, _CV2_OK)


def _decode_with_pyzbar(image_bytes: bytes) -> list[dict]:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        from pyzbar import pyzbar  # type: ignore
    except Exception as e:
        log.warning("decode_with_pyzbar deps missing: %s", e)
        return []

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        return []

    out: list[dict] = []
    seen: set[str] = set()
    try:
        results = pyzbar.decode(frame)
    except Exception as e:
        log.warning("pyzbar.decode error: %s", e)
        return []

    for r in results:
        try:
            text = (r.data or b"").decode("utf-8", errors="replace").strip()
        except Exception:
            text = ""
        if not text or text in seen:
            continue
        seen.add(text)
        fmt = getattr(r, "type", "") or "QR_CODE"
        out.append({"text": text, "format": str(fmt)})
    return out


def _decode_with_cv2(image_bytes: bytes) -> list[dict]:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception as e:
        log.warning("decode_with_cv2 deps missing: %s", e)
        return []

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        return []

    detector = cv2.QRCodeDetector()
    out: list[dict] = []
    seen: set[str] = set()
    try:
        ok, decoded_info, _points, _ = detector.detectAndDecodeMulti(frame)
        if ok and decoded_info:
            for txt in decoded_info:
                t = (txt or "").strip()
                if t and t not in seen:
                    seen.add(t)
                    out.append({"text": t, "format": "QR_CODE"})
    except Exception:
        pass

    if not out:
        try:
            txt, _points, _ = detector.detectAndDecode(frame)
            t = (txt or "").strip()
            if t:
                out.append({"text": t, "format": "QR_CODE"})
        except Exception:
            pass
    return out


def decode_qr_codes(image_bytes: bytes) -> list[dict]:
    """Decode QR/barcode. Thứ tự: pyzbar → cv2 fallback. Trả list[{text,format}], rỗng nếu không thấy."""
    if not image_bytes:
        return []
    if _PYZBAR_OK:
        codes = _decode_with_pyzbar(image_bytes)
        if codes:
            return codes
    if _CV2_OK:
        return _decode_with_cv2(image_bytes)
    log.warning("QR decode: cả pyzbar và cv2 đều unavailable")
    return []


class QRHistory:
    """Lưu lịch sử JSONL + dedupe trong N giây."""

    def __init__(self, path, *, dedupe_window_sec: float = 4.0, max_in_memory: int = 200) -> None:
        self.path = Path(path)
        self.dedupe_window_sec = float(dedupe_window_sec)
        self.max_in_memory = int(max_in_memory)
        self._lock = threading.Lock()
        self._cache: list[dict] = []
        self._last_seen: dict[str, float] = {}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            log.warning("QRHistory: không tạo được thư mục %s: %s", self.path.parent, e)
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            tail: list[dict] = []
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        tail.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            self._cache = tail[-self.max_in_memory:]
            log.info("QRHistory: nạp %d bản ghi từ %s", len(self._cache), self.path)
        except OSError as e:
            log.warning("QRHistory load error: %s", e)

    def _persist(self, entry: dict) -> None:
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            log.warning("QRHistory persist error: %s", e)

    def is_duplicate(self, text: str, window_sec: float | None = None) -> bool:
        if not text:
            return False
        w = float(window_sec) if window_sec is not None else self.dedupe_window_sec
        if w <= 0:
            return False
        now = time.monotonic()
        with self._lock:
            last = self._last_seen.get(text)
            return last is not None and (now - last) < w

    def append(self, source: str, text: str, format: str = "QR_CODE", fed_to_chat: bool = False) -> dict:
        ts_iso = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        entry = {"ts": ts_iso, "source": source, "text": text, "format": format, "fed_to_chat": bool(fed_to_chat)}
        with self._lock:
            self._cache.append(entry)
            if len(self._cache) > self.max_in_memory:
                self._cache = self._cache[-self.max_in_memory:]
            self._last_seen[text] = time.monotonic()
        self._persist(entry)
        return entry

    def list(self, limit: int = 50) -> list[dict]:
        with self._lock:
            if limit <= 0 or limit >= len(self._cache):
                return list(self._cache)
            return list(self._cache[-limit:])

    def clear(self) -> int:
        with self._lock:
            n = len(self._cache)
            self._cache.clear()
            self._last_seen.clear()
        try:
            if self.path.is_file():
                self.path.unlink()
        except OSError as e:
            log.warning("QRHistory clear: %s", e)
        return n


def short_for_speech(text: str, max_len: int = 160) -> str:
    """Tỉa nội dung QR cho TTS/reply: bỏ scheme http(s)://, cắt độ dài."""
    if not text:
        return ""
    t = text.strip()
    low = t.lower()
    if low.startswith("https://"):
        t = t[8:]
    elif low.startswith("http://"):
        t = t[7:]
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def looks_like_url(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    return t.startswith("http://") or t.startswith("https://")
