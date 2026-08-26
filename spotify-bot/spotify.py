"""
spotify.py — سرویس اسپاتیفای

دو لایهٔ کار دارد:

1) Spotify Web API رسمی — اگر SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET
   در .env ثبت شده باشد (برای آلبوم و پلی‌لیست بسیار توصیه می‌شود).

2) FALLBACK رایگان بدون کلید:
   - endpoint رسمی oEmbed برای متادیتای تک‌آهنگ (بدون token)
   - برش `window.__data` از صفحهٔ وب اسپاتیفای برای لیست آهنگ‌ها (best-effort)
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import List, Optional

import aiohttp

from models import KIND_ALBUM, KIND_PLAYLIST, Collection, Track

logger = logging.getLogger("spotify")

API_BASE = "https://api.spotify.com/v1"
OEMBED_URL = "https://open.spotify.com/oembed"
TOKEN_URL = "https://accounts.spotify.com/api/token"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TRACK_ID_RE = re.compile(r"^[A-Za-z0-9]{22}$")
DATA_RE = re.compile(r"window\.__data\s*=\s*(\{.*?\})\s*;?\s*</script>", re.S)


class SpotifyError(Exception):
    """خطایی که می‌توان مستقیم به کاربر نشان داد"""


class SpotifyService:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self._http = session
        self._cid = client_id
        self._csecret = client_secret
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    # ------------------------------------------------------------------ token
    @property
    def api_enabled(self) -> bool:
        return bool(self._cid and self._csecret)

    async def _get_token(self) -> str:
        """token با کش — client_credentials، بدون نیاز به user"""
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        async with self._http.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=aiohttp.BasicAuth(login=self._cid, password=self._csecret),
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status == 401:
                raise SpotifyError(
                    "کلیدهای اسپاتیفای اشتباه است (401).\n"
                    "SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET را در .env چک کن."
                )
            resp.raise_for_status()
            data = await resp.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + int(data.get("expires_in", 3600))
        return self._token

    async def _api(self, path: str) -> dict:
        token = await self._get_token()
        url = path if path.startswith("http") else f"{API_BASE}{path}"
        async with self._http.get(
            url,
            headers={"Authorization": f"Bearer {token}", "User-Agent": UA},
            timeout=aiohttp.ClientTimeout(total=25),
        ) as resp:
            if resp.status == 404:
                raise SpotifyError("این آیتم در اسپاتیفای پیدا نشد (404). شاید خصوصی یا حذف شده باشد.")
            if resp.status == 429:
                raise SpotifyError("اسپاتیفای موقتاً درخواست ما را ریجکت کرد (429). چند ثانیه دیگه امتحان کن.")
            if resp.status == 403:
                raise SpotifyError("دسترسی به این آیتم محدود است (403).")
            resp.raise_for_status()
            return await resp.json()

    # ------------------------------------------------------------------- parse
    @staticmethod
    def _artists_of(item: dict) -> str:
        return ", ".join(
            a.get("name", "") for a in item.get("artists", []) if isinstance(a, dict)
        )

    @staticmethod
    def _track_image(track: dict) -> str:
        images = ((track.get("album") or {}).get("images")) or []
        return images[0]["url"] if images and isinstance(images[0], dict) else ""

    @staticmethod
    def _collection_image(coll: dict) -> str:
        images = coll.get("images") or []
        return images[0]["url"] if images and isinstance(images[0], dict) else ""

    def _to_track(self, d: dict) -> Track:
        return Track(
            id=d["id"],
            title=d.get("name", "?"),
            artist=self._artists_of(d),
            duration_sec=int(d.get("duration_ms", 0) // 1000),
            image_url=self._track_image(d),
            album=(d.get("album") or {}).get("name", ""),
        )

    # ------------------------------------------------------------- official API
    async def fetch_track(self, track_id: str) -> Track:
        d = await self._api(f"/tracks/{track_id}")
        return self._to_track(d)

    async def fetch_album(self, album_id: str) -> Collection:
        d = await self._api(f"/albums/{album_id}")
        items: List[dict] = list(d.get("tracks", {}).get("items", []))
        url = (d.get("tracks") or {}).get("next")
        while url:  # صفحه‌بندی آهنگ‌های آلبوم
            d2 = await self._api(url)
            items += d2.get("tracks", {}).get("items", [])
            url = d2.get("tracks", {}).get("next")
        tracks = [self._to_track(it) for it in items if it.get("id")]
        return Collection(
            kind=KIND_ALBUM,
            id=album_id,
            title=d.get("name", "آلبوم"),
            tracks=tracks,
            total=len(tracks),
            image_url=self._collection_image(d),
        )

    async def fetch_playlist(self, playlist_id: str) -> Collection:
        d = await self._api(f"/playlists/{playlist_id}")
        items: List[dict] = list(d.get("tracks", {}).get("items", []))
        url = (d.get("tracks") or {}).get("next")
        while url:  # صفحه‌بندی آیتم‌های پلی‌لیست
            d2 = await self._api(url)
            items += d2.get("tracks", {}).get("items", [])
            url = d2.get("tracks", {}).get("next")
        tracks: List[Track] = []
        for it in items:
            t = it.get("track") or {}
            # پادکست/اپیزود و آیتم‌های نامعتبر رد می‌شوند
            if t.get("type") not in (None, "track") or not t.get("id"):
                continue
            tracks.append(self._to_track(t))
        return Collection(
            kind=KIND_PLAYLIST,
            id=playlist_id,
            title=d.get("name", "پلی‌لیست"),
            tracks=tracks,
            total=len(tracks),
            image_url=self._collection_image(d),
        )

    # ---------------------------------------------------------------- fallback
    async def _oembed(self, url: str) -> Optional[dict]:
        """oEmbed رسمی اسپاتیفیا — بدون نیاز به کلید"""
        try:
            async with self._http.get(
                OEMBED_URL,
                params={"url": url},
                headers={"User-Agent": UA},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except Exception as e:  # noqa: BLE001
            logger.debug("oembed failed: %s", e)
            return None

    async def _scrape_data(self, url: str) -> Optional[dict]:
        """برداشتن `window.__data` از صفحهٔ وب اسپاتیفای (بدون کلید)"""
        try:
            async with self._http.get(
                url,
                headers={"User-Agent": UA, "Accept-Language": "en"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    return None
                html_text = await resp.text()
        except Exception:  # noqa: BLE001
            return None
        m = DATA_RE.search(html_text)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None

    def _walk_tracks(self, obj, out: List[Track], seen: set) -> None:
        """ورود بازگشتی به JSON صفحه — پیدا کردن همهٔ track ها"""
        if isinstance(obj, dict):
            tid, name, uri = obj.get("id"), obj.get("name"), obj.get("uri")
            if (
                isinstance(tid, str)
                and isinstance(name, str)
                and isinstance(uri, str)
                and TRACK_ID_RE.match(tid)
                and "track" in uri
                and tid not in seen
            ):
                artists = obj.get("artists")
                if isinstance(artists, list):
                    artist = ", ".join(
                        a.get("name", "") if isinstance(a, dict) else str(a) for a in artists
                    )
                elif isinstance(artists, str):
                    artist = artists
                else:
                    artist = obj.get("primary_artist_name") or obj.get("artist") or ""
                dur = obj.get("duration_ms") or 0
                try:
                    dur = int(dur) // 1000
                except (TypeError, ValueError):
                    dur = 0
                seen.add(tid)
                out.append(Track(id=tid, title=name, artist=str(artist), duration_sec=dur))
            for v in obj.values():
                self._walk_tracks(v, out, seen)
        elif isinstance(obj, list):
            for v in obj:
                self._walk_tracks(v, out, seen)

    def _find_playlist_title(self, obj) -> str:
        if isinstance(obj, dict):
            pl = obj.get("playlist")
            if isinstance(pl, dict) and pl.get("name"):
                return str(pl["name"])
            if str(obj.get("uri", "")).startswith("spotify:playlist:") and obj.get("name"):
                return str(obj["name"])
            for v in obj.values():
                found = self._find_playlist_title(v)
                if found:
                    return found
        elif isinstance(obj, list):
            for v in obj:
                found = self._find_playlist_title(v)
                if found:
                    return found
        return ""

    # ------------------------------------------------------- public interface
    async def track(self, track_id: str) -> Track:
        """تک‌آهنگ — اول API رسمی، در نبود کلید oEmbed"""
        if self.api_enabled:
            return await self.fetch_track(track_id)
        meta = await self._oembed(f"https://open.spotify.com/track/{track_id}")
        if meta and meta.get("title"):
            title = meta["title"]
            artist = meta.get("author", "")
            # گاهی oEmbed «عنوان - آرتیست» برمی‌گرداند
            if "-" in title and artist:
                first_artist = artist.split(",")[0].strip()
                if title.endswith(f" - {first_artist}"):
                    title = title[: -len(first_artist) - 3]
            return Track(
                id=track_id,
                title=title,
                artist=artist,
                image_url=meta.get("thumbnail_url", ""),
            )
        raise SpotifyError(
            "متادیتای این آهنگ را پیدا نکردم.\n"
            "لینک را دوباره چک کن یا کلید API اسپاتیفای را در .env بگذار."
        )

    async def collection(self, kind: str, coll_id: str) -> Collection:
        """آلبوم / پلی‌لیست — اول API رسمی، در نبود کلید اسکرپ best-effort"""
        if self.api_enabled:
            if kind == KIND_ALBUM:
                return await self.fetch_album(coll_id)
            return await self.fetch_playlist(coll_id)

        base = f"https://open.spotify.com/{kind}/{coll_id}"
        meta = await self._oembed(base)
        title = (meta or {}).get("title") or ""
        data = await self._scrape_data(base)
        if data is None:
            data = await self._scrape_data(f"https://open.spotify.com/embed/{kind}/{coll_id}")

        found: List[Track] = []
        if data is not None:
            self._walk_tracks(data, found, set())
            if kind == KIND_PLAYLIST:
                t2 = self._find_playlist_title(data)
                if t2:
                    title = t2

        if not found:
            raise SpotifyError(
                "بدون کلید رسمی API، لیست آهنگ‌های آلبوم/پلی‌لیست خوانده نمی‌شود.\n"
                "راه حل: در developer.spotify.com یک اپ رایگان بساز و\n"
                "<code>SPOTIFY_CLIENT_ID</code> و <code>SPOTIFY_CLIENT_SECRET</code> را در .env بگذار.\n"
                "(دانلود <b>تک‌آهنگ</b> بدون کلید هم کاملاً کار می‌کند.)"
            )
        return Collection(
            kind=kind,
            id=coll_id,
            title=title or ("آلبوم" if kind == KIND_ALBUM else "پلی‌لیست"),
            tracks=found,
            total=len(found),
            image_url=(meta or {}).get("thumbnail_url", ""),
        )
