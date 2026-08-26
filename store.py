"""
store.py — ذخیره‌ی ماندگار آمار و تنظیمات کاربر (JSON + قفل + نوشتن اتمیک)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict

from utils import human_size, to_fa

logger = logging.getLogger("store")


class JsonStore:
    """
    یک فایل JSON ساده با lock برای دسترسی هم‌زمان.
    هر بار با نوشتن موقت + rename جایگزین می‌شود تا خراب نشود.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            logger.warning("فایل ذخیره‌ساز خراب بود؛ دوباره ساخته می‌شود: %s", self.path)
            return {}

    async def _save_locked(self, data: Dict[str, Any]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    async def update(self, fn: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
        """خواندن → تغییر → ذخیره، همه زیر یک قفل"""
        async with self._lock:
            data = await self.load()
            fn(data)
            await self._save_locked(data)
            return data


class Stats:
    """آمار کلی ربات"""

    DEFAULTS: Dict[str, Any] = {
        "tracks": 0,
        "albums": 0,
        "playlists": 0,
        "failed": 0,
        "bytes_sent": 0,
        "users": {},
    }

    def __init__(self, path: str):
        self._store = JsonStore(path)

    async def record(
        self,
        kind: str,
        ok: bool = True,
        n_tracks: int = 0,
        nbytes: int = 0,
        user_id: int | None = None,
    ) -> None:
        def _apply(data: Dict[str, Any]) -> None:
            base = dict(self.DEFAULTS)
            base.update(data)
            if ok:
                base[kind] = base.get(kind, 0) + 1
                base["tracks"] = base.get("tracks", 0) + n_tracks
                base["bytes_sent"] = base.get("bytes_sent", 0) + nbytes
            else:
                base["failed"] = base.get("failed", 0) + 1
            if user_id:
                users = base.setdefault("users", {})
                users[str(user_id)] = users.get(str(user_id), 0) + 1
            data.clear()
            data.update(base)

        await self._store.update(_apply)

    async def summary(self) -> str:
        data = await self._store.load()
        base = dict(self.DEFAULTS)
        base.update(data)
        total = base.get("tracks", 0) + base.get("albums", 0) + base.get("playlists", 0)
        return (
            "📊 <b>آمار اسپاتی‌دانلودر</b>\n\n"
            f"🎵 آهنگ: <b>{to_fa(base.get('tracks', 0))}</b>\n"
            f"💿 آلبوم: <b>{to_fa(base.get('albums', 0))}</b>\n"
            f"📃 پلی‌لیست: <b>{to_fa(base.get('playlists', 0))}</b>\n"
            f"✅ موفق: <b>{to_fa(total)}</b> | ❌ ناموفق: <b>{to_fa(base.get('failed', 0))}</b>\n"
            f"💾 حجم کل ارسالی: <b>{human_size(base.get('bytes_sent', 0))}</b>\n"
            f"👥 کاربران فعال: <b>{to_fa(len(base.get('users', {})))}</b>"
        )


class UserSettings:
    """تنظیمات هر کاربر (کیفیت پیش‌فرض)"""

    ALLOWED = (128, 192, 320)

    def __init__(self, path: str):
        self._store = JsonStore(path)

    async def get_quality(self, user_id: int, default: int) -> int:
        data = await self._store.load()
        q = data.get(str(user_id), {}).get("quality")
        return q if q in self.ALLOWED else default

    async def set_quality(self, user_id: int, quality: int) -> None:
        def _apply(data: Dict[str, Any]) -> None:
            data.setdefault(str(user_id), {})["quality"] = quality

        await self._store.update(_apply)
