"""
config.py — بارگذاری تنظیمات از متغیرهای محیطی / فایل .env

همه‌ی تنظیمات ربات از همین‌جا می‌آید؛ هیچ مقداری در کد hard-code نیست.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _str(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _int(name: str, default: int) -> int:
    try:
        return int(_str(name, "") or default)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(_str(name, "") or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """تنظیمات ثابت برنامه (frozen = غیرقابل تغییر در runtime)"""

    bot_token: str

    # Spotify Web API — اختیاری، ولی برای آلبوم/پلی‌لیست ضروری است
    spotify_client_id: Optional[str]
    spotify_client_secret: Optional[str]

    # دانلود
    default_quality_kbps: int      # کیفیت پیش‌فرض MP3 (128/192/320)
    default_format: str            # mp3 | m4a
    max_tracks_per_job: int        # سقف آهنگ در هر سفارش
    telegram_file_limit_mb: int    # سقف آپلود بوت‌های تلگرام
    download_dir: str              # پوشهٔ فایل‌های موقت
    rate_limit_seconds: float      # فاصلهٔ بین دو دانلود در یک چت
    job_ttl_seconds: int           # اعتبار دکمه‌های شیشه‌ای
    log_level: str

    @property
    def spotify_api_enabled(self) -> bool:
        return bool(self.spotify_client_id and self.spotify_client_secret)


def load_config() -> Config:
    token = _str("BOT_TOKEN")
    if not token:
        raise SystemExit(
            "❌ BOT_TOKEN پیدا نشد!\n"
            "فایل .env را از .env.example کپی کن و توکن رباتت را داخلش بنویس.\n"
            "توکن را از @BotFather بگیر."
        )

    quality = _int("DEFAULT_QUALITY", 192)
    if quality not in (128, 192, 320):
        quality = 192

    fmt = (_str("DEFAULT_FORMAT", "mp3") or "mp3").lower()
    if fmt not in ("mp3", "m4a"):
        fmt = "mp3"

    return Config(
        bot_token=token,
        spotify_client_id=_str("SPOTIFY_CLIENT_ID"),
        spotify_client_secret=_str("SPOTIFY_CLIENT_SECRET"),
        default_quality_kbps=quality,
        default_format=fmt,
        max_tracks_per_job=max(1, _int("MAX_TRACKS_PER_JOB", 20)),
        telegram_file_limit_mb=max(1, _int("TELEGRAM_FILE_LIMIT_MB", 49)),
        download_dir=_str("DOWNLOAD_DIR", "downloads") or "downloads",
        rate_limit_seconds=max(0.0, _float("RATE_LIMIT_SECONDS", 15)),
        job_ttl_seconds=max(60, _int("JOB_TTL_SECONDS", 900)),
        log_level=(_str("LOG_LEVEL", "INFO") or "INFO").upper(),
    )
