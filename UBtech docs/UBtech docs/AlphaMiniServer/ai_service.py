"""
ai_service.py — LLM Service với Conversation Memory
Hỗ trợ Groq (miễn phí), Gemini và OpenAI. Tự động parse emotion tag.
"""

import re
import logging
from config import (
    LLM_PROVIDER, GEMINI_API_KEY, OPENAI_API_KEY, GROQ_API_KEY,
    SYSTEM_PROMPT, MAX_HISTORY_TURNS
)

log = logging.getLogger("AIService")


class AIService:
    """
    Quản lý kết nối LLM và lịch sử hội thoại.
    conversation_history: list[{"role": "user"|"assistant", "content": str}]
    """

    def __init__(self):
        self.conversation_history: list[dict] = []
        self.model = None
        self.chat_session = None
        self.openai_client = None
        self._ready = False
        self._init_llm()

    def _init_llm(self):
        try:
            # ── Groq (miễn phí, nhanh nhất) ──────────────────────────────────
            if LLM_PROVIDER == "groq":
                from groq import AsyncGroq
                if GROQ_API_KEY == "YOUR_GROQ_API_KEY_HERE":
                    log.warning("⚠️  Groq API key chưa điền! Vào console.groq.com/keys để lấy key miễn phí.")
                    return
                self._groq_client = AsyncGroq(api_key=GROQ_API_KEY)
                # llama-3.3-70b-versatile: model tốt nhất miễn phí của Groq
                self._groq_model = "llama-3.3-70b-versatile"
                self._ready = True
                log.info(f"✅ Groq [{self._groq_model}] sẵn sàng (FREE - 14400 req/ngày)")

            elif LLM_PROVIDER == "gemini":
                # Dùng google-genai (thư viện mới, thay thế google-generativeai cũ)
                from google import genai
                from google.genai import types as genai_types
                if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
                    log.warning("⚠️  Gemini API key chưa được cấu hình trong config.py!")
                    return
                self._genai_client = genai.Client(api_key=GEMINI_API_KEY)
                self._genai_types  = genai_types
                # Thử model theo thứ tự ưu tiên
                self._gemini_model = "gemini-2.0-flash-lite"
                self._ready = True
                log.info(f"✅ Gemini sẵn sàng (model: {self._gemini_model})")

            elif LLM_PROVIDER == "openai":
                from openai import AsyncOpenAI
                if OPENAI_API_KEY == "YOUR_OPENAI_API_KEY_HERE":
                    log.warning("⚠️  OpenAI API key chưa được cấu hình trong config.py!")
                    return
                self.openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
                self._ready = True
                log.info("✅ OpenAI GPT-4o-mini sẵn sàng")

        except ImportError as e:
            log.error(f"Thiếu thư viện: {e}. Chạy: pip install -r requirements.txt")
        except Exception as e:
            log.error(f"Lỗi khởi tạo LLM: {e}")

    # ── Public API ─────────────────────────────────────────────────────────────

    async def chat(self, user_message: str) -> dict:
        """
        Gửi tin nhắn, nhận phản hồi từ LLM.
        Trả về: {"text": str, "emotion": str, "raw": str}
        """
        if not self._ready:
            return self._fallback_response("LLM chưa sẵn sàng. Kiểm tra API key trong config.py")

        log.info(f"User → LLM: {user_message}")
        try:
            if LLM_PROVIDER == "groq":
                raw = await self._groq_chat(user_message)
            elif LLM_PROVIDER == "gemini":
                raw = await self._gemini_chat(user_message)
            else:
                raw = await self._openai_chat(user_message)

            text, emotion, ai_actions = self._parse_tags(raw)
            log.info(f"LLM → [{emotion}] actions={ai_actions}: {text}")

            # Lưu vào history
            self.conversation_history.append({"role": "user",      "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": text})

            # Giới hạn độ dài history
            max_msgs = MAX_HISTORY_TURNS * 2
            if len(self.conversation_history) > max_msgs:
                self.conversation_history = self.conversation_history[-max_msgs:]

            return {"text": text, "emotion": emotion, "actions": ai_actions, "raw": raw}

        except Exception as e:
            log.error(f"LLM error: {e}", exc_info=True)
            return self._fallback_response(str(e))

    def clear_history(self):
        """Reset conversation — bắt đầu cuộc trò chuyện mới."""
        self.conversation_history = []
        if LLM_PROVIDER == "gemini" and self.model:
            self.chat_session = self.model.start_chat(history=[])
        log.info("🔄 Lịch sử hội thoại đã được xóa")

    def get_history(self) -> list[dict]:
        return self.conversation_history

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ── LLM backends ──────────────────────────────────────────────────────────

    async def _groq_chat(self, message: str) -> str:
        """Groq API — OpenAI-compatible, miễn phí, cực nhanh (~0.3s/response)."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        # Gửi kèm history để giữ ngữ cảnh
        for h in self.conversation_history[-(MAX_HISTORY_TURNS * 2):]:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        response = await self._groq_client.chat.completions.create(
            model=self._groq_model,
            messages=messages,
            max_tokens=250,
            temperature=0.85,
        )
        return response.choices[0].message.content

    async def _gemini_chat(self, message: str) -> str:
        # Xây dựng nội dung với history để giữ context
        contents = []
        for h in self.conversation_history[-(MAX_HISTORY_TURNS * 2):]:
            role = "user" if h["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": h["content"]}]})
        contents.append({"role": "user", "parts": [{"text": message}]})

        config = self._genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=250,
            temperature=0.85,
        )

        # Thử các model fallback nếu bị rate limit
        models_to_try = [
            self._gemini_model,
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "gemini-flash-lite-latest",
        ]

        last_err = None
        for model in models_to_try:
            try:
                response = self._genai_client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                if model != self._gemini_model:
                    log.info(f"Switched to model: {model}")
                    self._gemini_model = model
                return response.text
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    log.warning(f"Rate limit on {model}, trying next…")
                    last_err = e
                    continue
                raise  # Lỗi khác thì raise ngay

        raise last_err or Exception("All Gemini models rate limited")

    async def _openai_chat(self, message: str) -> str:
        # OpenAI: gửi full history thủ công
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        # Chỉ gửi MAX_HISTORY_TURNS turn gần nhất
        recent = self.conversation_history[-(MAX_HISTORY_TURNS * 2):]
        for h in recent:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        response = await self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=250,
            temperature=0.85,
        )
        return response.choices[0].message.content

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_tags(text: str) -> tuple[str, str, list[str]]:
        """
        Tách EMOTION và ACTION tags ra khỏi text AI.
        "Nhảy nào! [EMOTION:dance][ACTION:nhảy]"
        → ("Nhảy nào!", "dance", ["nhảy"])
        """
        # Parse EMOTION
        emotion_match = re.search(r'\[EMOTION:(\w+)\]', text)
        emotion = emotion_match.group(1).lower() if emotion_match else "happy"
        valid_emotions = {"happy", "sad", "surprised", "thinking", "dance", "wave"}
        if emotion not in valid_emotions:
            emotion = "happy"

        # Parse ACTION tags (có thể nhiều)
        ai_actions = re.findall(r'\[ACTION:([^\]]+)\]', text)
        ai_actions = [a.strip().lower() for a in ai_actions]

        # Xóa tất cả tags khỏi text
        clean = re.sub(r'\[(EMOTION|ACTION):[^\]]+\]', '', text).strip()
        return clean, emotion, ai_actions

    @staticmethod
    def _fallback_response(reason: str) -> dict:
        return {
            "text":    "Xin lỗi, tôi đang gặp sự cố kỹ thuật. Bạn thử lại sau nhé!",
            "emotion": "sad",
            "actions": [],
            "raw":     reason,
        }
