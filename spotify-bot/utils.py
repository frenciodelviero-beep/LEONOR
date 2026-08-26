"""
utils.py — توابع کمکی: پارس لینک، اعداد فارسی، فرمت زمان، نوار پیشرفت، rate-limit
"""
from __future__ import annotations

import html
import re
import time
import uuid
from typing import Optional, Tuple

# https://open.spotify.com/track/123abc...  |  spotify:track:123abc...
_SPOTIFY_URL_RE = re.compile(
    r"(?:open\.)?spotify\.com/(track|album|playlist)/([A-Za-z0-9]{8,32})"
)
_SPOTIFY_URI_RE = re.compile(r"spotify:(track|album|playlist):([A-Za-z0-9]{8,32})")

_FARSI_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def parse_spotify_url(text: str) -> Optional[Tuple[str, str]]:
    """اگر متن حاوی لینک/URI اسپاتیفای بود → (نوع، آیدی) وگرنه None"""
    if not text:
        return None
    for regex in (_SPOTIFY_URL_RE, _SPOTIFY_URI_RE):
        m = regex.search(text)
        if m:
            return m.group(1), m.group(2)
    return None


def new_job_id() -> str:
    return uuid.uuid4().hex[:10]


def to_fa(text: str) -> str:
    """تبدیل ارقام لاتین به فارسی (برای زیبایی UI)"""
    return str(text).translate(_FARSI_DIGITS)


def format_duration(total_sec: int) -> str:
    if total_sec <= 0:
        return "—"
    h, rem = divmod(int(total_sec), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def human_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            return f"{to_fa(f'{num_bytes:.1f}')} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} GB"


def esc(text: str) -> str:
    """escape برای parse_mode=HTML"""
    return html.escape(str(text), quote=False)


def clip(text: str, limit: int = 80) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def safe_filename(text: str, max_len: int = 60) -> str:
    text = re.sub(r"[\\/:*?\"<>|]+", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len] or "audio"


def progress_bar(pct: int, width: int = 14) -> str:
    pct = max(0, min(100, int(pct)))
    filled = round(width * pct / 100)
    return "▰" * filled + "▱" * (width - filled)


def bot_mentioned(text: str, bot_username: str) -> bool:
    return bool(bot_username) and f"@{bot_username}" in (text or "")


class ChatCooldown:
    """ریط‌لیمت ساده: حداقل فاصله بین دو درخواست دانلود در هر چت"""

    def __init__(self, seconds: float):
        self._seconds = seconds
        self._last: dict[int, float] = {}

    def check(self, chat_id: int) -> Tuple[bool, float]:
        """برمی‌گرداند (آیا مجاز؟، ثانیهٔ باقی‌مانده)"""
        if self._seconds <= 0:
            return True, 0.0
        now = time.monotonic()
        last = self._last.get(chat_id)
        if last is None or now - last >= self._seconds:
            return True, 0.0
        return False, self._seconds - (now - last)

    def mark(self, chat_id: int) -> None:
        self._last[chat_id] = time.monotonic()
