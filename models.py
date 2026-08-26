"""
models.py — ساختارهای داده‌ای مشترک بین ماژول‌ها
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

KIND_TRACK = "track"
KIND_ALBUM = "album"
KIND_PLAYLIST = "playlist"

KIND_LABELS_FA = {
    KIND_TRACK: "🎵 آهنگ",
    KIND_ALBUM: "💿 آلبوم",
    KIND_PLAYLIST: "📃 پلی‌لیست",
}


@dataclass
class Track:
    """یک آهنگ — از API اسپاتیفیا یا از oEmbed/اسکرپ"""

    id: str
    title: str
    artist: str
    duration_sec: int = 0
    image_url: str = ""
    album: str = ""

    @property
    def query(self) -> str:
        """استرینگ جستجو در یوتیوب"""
        return f"{self.title} {self.artist}".strip()

    def short_info(self) -> str:
        return f"{self.title} — {self.artist}" if self.artist else self.title


@dataclass
class Collection:
    """آلبوم یا پلی‌لیست با لیست آهنگ‌هایش"""

    kind: str
    id: str
    title: str
    tracks: List[Track] = field(default_factory=list)
    total: int = 0          # تعداد کل (قبل از truncation)
    image_url: str = ""
