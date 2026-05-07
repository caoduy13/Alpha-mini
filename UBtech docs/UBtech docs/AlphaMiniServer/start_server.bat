@echo off
title Alpha Mini AI Chatbot Server
color 0A
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║    Alpha Mini AI Chatbot Server v2.0     ║
echo  ║    FastAPI + Gemini/GPT + alphamini SDK  ║
echo  ╚══════════════════════════════════════════╝
echo.

:: ── Check Python (use local user install) ─────────────
set "PY_EXE=C:\Users\Asus\AppData\Local\Python\bin\python3.exe"
if not exist "%PY_EXE%" (
    echo [ERROR] Python executable not found at:
    echo         %PY_EXE%
    echo   Please adjust PY_EXE path in start_server.bat or install Python.
    pause
    exit /b 1
)

:: ── Install / update dependencies ────────────────────
echo [1/4] Installing dependencies...
"%PY_EXE%" -m pip install -r requirements.txt -q --no-warn-script-location
if errorlevel 1 (
    echo [WARNING] Some packages may have failed. Continuing...
)
echo       Done.

:: ── Show API key status ───────────────────────────────
echo.
echo [2/4] API Key status:
"%PY_EXE%" -c "from config import GEMINI_API_KEY, OPENAI_API_KEY, LLM_PROVIDER; print(f'  Provider : {LLM_PROVIDER}'); print(f'  Gemini   : {\"SET\" if GEMINI_API_KEY else \"NOT SET\"}'); print(f'  OpenAI   : {\"SET\" if OPENAI_API_KEY else \"NOT SET\"}')"
echo.
echo   To set Gemini key: edit config.py  OR  set GEMINI_API_KEY=your-key
echo   Get free key at: https://aistudio.google.com/app/apikey

:: ── Show local IP ─────────────────────────────────────
echo.
echo [3/4] Your local IP (enter this in the Flutter app):
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    echo    ^>^>^>  %%a
)

:: ── Fix alphamini protobuf compatibility ───────────────
set PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

:: ── Start server ──────────────────────────────────────
echo.
echo [4/4] Starting server...
echo   WebSocket : ws://YOUR_IP:8000/ws/chat
echo   REST API  : http://YOUR_IP:8000/status
echo   API Docs  : http://YOUR_IP:8000/docs
echo.
echo  Make sure Alpha Mini is ON and on the same WiFi!
echo  Press Ctrl+C to stop.
echo.

rem Chay uvicorn KHONG dung --reload de tranh loi event loop / UDP bind lai
call "%PY_EXE%" -m uvicorn server:app --host 0.0.0.0 --port 8000
pause
