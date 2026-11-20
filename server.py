"""
Judgemental Padosi Aunty — Render-ready backend.

FastAPI app wrapping a single shared AuntyBot instance with:
  * per-visitor rate limits (daily + per-minute)
  * site-wide daily limit
  * per-session fact tracking (swapped onto the shared bot under a lock)
  * CORS so the frontend can call it cross-origin
  * serves the HTML frontend at /

Limits are constants at the top, overridable via environment variables.
"""

import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import config
from aunty_core import AuntyBot


# ---------------------------------------------------------------------------
# Limits (override via environment variables)
# ---------------------------------------------------------------------------
PER_VISITOR_DAILY = int(os.getenv("AUNTY_PER_VISITOR_DAILY", "8"))
SITE_DAILY = int(os.getenv("AUNTY_SITE_DAILY", "45"))
MAX_MESSAGE_CHARS = int(os.getenv("AUNTY_MAX_MESSAGE_CHARS", "300"))
PER_VISITOR_PER_MINUTE = int(os.getenv("AUNTY_PER_VISITOR_PER_MINUTE", "6"))
MAX_SESSION_ID_LEN = int(os.getenv("AUNTY_MAX_SESSION_ID_LEN", "64"))

# Render injects PORT; fall back to 8000 for local dev.
PORT = int(os.getenv("PORT", "8000"))


# ---------------------------------------------------------------------------
# Shared bot + in-memory state
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_bot = None
_bot_ready = False

# visitor_key -> {"day": date, "count": int, "minute": str, "minute_count": int, "used_ids": set}
_visitor_state = {}
_site_day = None
_site_count = 0


class ChatRequest(BaseModel):
    session_id: str
    message: str


def _today() -> date:
    return datetime.now().date()


def _minute_key() -> str:
    return datetime.now().strftime("%Y%m%d%H%M")


def _reset_daily_if_needed() -> None:
    global _site_day, _site_count
    today = _today()
    if _site_day is None or _site_day != today:
        _site_day = today
        _site_count = 0
    for st in _visitor_state.values():
        if st["day"] != today:
            st["day"] = today
            st["count"] = 0
            st["minute"] = _minute_key()
            st["minute_count"] = 0


def _visitor_key(session_id: str, request: Request) -> str:
    ip = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "unknown")
    return f"{ip}|{session_id}"


def _aunty_limit_message() -> str:
    return (
        "Arre beta, itni jaldi? Shubh finishes his whole chapter before you send your eighth message. "
        "Come back tomorrow, or at least after tea-time. Tauba tauba."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bot, _bot_ready
    try:
        _bot = AuntyBot(debug=False)
        _bot_ready = True
    except (Exception, SystemExit):  # no API key, stale index, etc. — never expose internals or the key
        _bot = None
        _bot_ready = False
    _reset_daily_if_needed()
    yield
    _bot = None
    _bot_ready = False


app = FastAPI(title="Judgemental Padosi Aunty", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIR = Path(__file__).resolve().parent / "web"


@app.get("/")
async def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
async def health():
    return {"ok": True, "ready": _bot_ready}


@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    if not _bot_ready or _bot is None:
        return JSONResponse(
            status_code=503,
            content={
                "reply": "The aunty is not set up yet. The owner needs to add an OpenRouter key on Render and redeploy.",
                "remaining": 0,
            },
        )

    # Cap session id length (ignore attempts to set something huge)
    session_id = (req.session_id or "anon").strip()[:MAX_SESSION_ID_LEN] or "anon"

    message = (req.message or "")
    if not message.strip():
        return JSONResponse(
            status_code=400,
            content={
                "reply": "Arre beta, you didn't say anything. Shubh at least opens his mouth to speak.",
                "remaining": 0,
            },
        )
    if len(message) > MAX_MESSAGE_CHARS:
        return JSONResponse(
            status_code=400,
            content={
                "reply": (
                    f"That's too long, beta. Keep it under {MAX_MESSAGE_CHARS} characters — "
                    "Shubh writes concise answers."
                ),
                "remaining": 0,
            },
        )

    vk = _visitor_key(session_id, request)
    today = _today()
    mk = _minute_key()

    global _site_count
    with _lock:
        _reset_daily_if_needed()

        st = _visitor_state.get(vk)
        if st is None:
            st = {"day": today, "count": 0, "minute": mk, "minute_count": 0, "used_ids": set()}
            _visitor_state[vk] = st

        # per-minute check
        if st["minute"] != mk:
            st["minute"] = mk
            st["minute_count"] = 0
        if st["minute_count"] >= PER_VISITOR_PER_MINUTE:
            return JSONResponse(
                status_code=429,
                content={"reply": _aunty_limit_message(), "remaining": 0},
            )

        # per-visitor daily check
        if st["count"] >= PER_VISITOR_DAILY:
            return JSONResponse(
                status_code=429,
                content={"reply": _aunty_limit_message(), "remaining": 0},
            )

        # site-wide daily check
        if _site_count >= SITE_DAILY:
            return JSONResponse(
                status_code=429,
                content={"reply": _aunty_limit_message(), "remaining": 0},
            )

        # Consume a slot
        st["count"] += 1
        st["minute_count"] += 1
        _site_count += 1

        # Per-session fact tracking: swap used_ids onto the shared bot, call reply
        used = st["used_ids"]
        _bot.used_ids = used
        try:
            reply = _bot.reply(message)
        except Exception:  # never expose stack traces or the key
            reply = "Arre beta, the aunty tripped over her own sari. Try again in a moment."

        remaining = max(0, PER_VISITOR_DAILY - st["count"])

    return {"reply": reply, "remaining": remaining}
