"""
downloader.py — جستجو در یوتیوب + دانلود صدا با yt-dlp

yt-dlp به‌صورت subprocess فراخوانی می‌شود؛ این کار با آپدیت‌های مکرر یوتیوب
سازگارتر از لایبریری‌های python است.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import shutil
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional

logger = logging.getLogger("downloader")

ProgressCb = Callable[[int, str], Awaitable[None]]


class DownloadError(Exception):
    """خطایی که می‌توان مستقیم به کاربر نشان داد"""


@dataclass
class VideoHit:
    url: str
    title: str
    duration_sec: int
    view_count: Optional[int]
    like_count: Optional[int]

    @property
    def yt_id(self) -> str:
        return self.url.rsplit("=", 1)[-1]


_TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)
_PCT_RE = re.compile(r"(\d{1,3})\.?\d*\s*%")


class Downloader:
    def __init__(self, work_dir: str, search_results: int = 12):
        self.work_dir = work_dir
        self.search_results = search_results
        os.makedirs(work_dir, exist_ok=True)
        # سقف هم‌زمانی دانلودها — روی سرور سنگین فشار نمی‌آوریم
        self._lock = asyncio.Semaphore(3)

        if shutil.which("yt-dlp") is None:
            raise SystemExit(
                "❌ yt-dlp پیدا نشد.\n"
                "با `pip install -r requirements.txt` نصبش کن (کنسول yt-dlp هم می‌آید)."
            )
        if shutil.which("ffmpeg") is None:
            raise SystemExit(
                "❌ ffmpeg پیدا نشد — برای تبدیل به MP3/M4A لازم است.\n"
                "دبیان/اوبونتو: `sudo apt install ffmpeg` | مک: `brew install ffmpeg`"
            )

    # ------------------------------------------------------------------ search
    async def _run(self, *cmd: str, timeout: float) -> bytes:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise DownloadError("زمان جستجو تمام شد؛ دوباره تلاش کن.")
        if proc.returncode != 0:
            tail = (err or b"").decode(errors="ignore")[-400:]
            logger.warning("yt-dlp search failed: %s", tail)
        return out

    async def search_youtube(
        self, query: str, target_duration: Optional[int] = None
    ) -> Optional[VideoHit]:
        """jستجوی yوتیوب + انتخاب بهترین نتیجه با امتیازدهی هوشمند"""
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "-J",
            f"ytsearch{self.search_results}:{query}",
        ]
        raw = await self._run(*cmd, timeout=60)
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        hits: List[VideoHit] = []
        for e in data.get("entries") or []:
            vid = e.get("id")
            if not vid:
                continue
            hits.append(
                VideoHit(
                    url=f"https://www.youtube.com/watch?v={vid}",
                    title=e.get("title") or "",
                    duration_sec=int(e.get("duration") or 0),
                    view_count=e.get("view_count"),
                    like_count=e.get("like_count"),
                )
            )

        best = self._score(hits, query, target_duration)
        if best:
            logger.info("best hit for %r: %s", query, best.title)
        return best

    @staticmethod
    def _score(
        hits: List[VideoHit], query: str, target: Optional[int]
    ) -> Optional[VideoHit]:
        """
        امتیازدهی به هر نتیجه:
          + همپوشانی توکن‌های عنوان/آرتیست با query
          + مدتی منطقی (۴۵ ثانیه تا ۲۵ دقیقه)
          + نزدیکی به مدت دقیق آهنگ (اگر از اسپاتیفیا داریم)
          + کمی وزن روی view_count / like_count
        """
        if not hits:
            return None

        def tokenize(s: str) -> set:
            return {t.lower() for t in _TOKEN_RE.findall(s or "") if len(t) > 1}

        q_tokens = tokenize(query)

        def score(h: VideoHit) -> float:
            s = 0.0
            t_tokens = tokenize(h.title)
            if q_tokens:
                s += 4.0 * (len(q_tokens & t_tokens) / len(q_tokens))
                if q_tokens <= t_tokens:
                    s += 1.5  # همهٔ کلمات query داخل عنوان است
            d = h.duration_sec
            if d:
                if 45 <= d <= 1500:
                    s += 1.0
                else:
                    s -= 2.0
                if target and target > 0:
                    diff = abs(d - target)
                    if diff <= 45:
                        s += 2.5
                    elif diff <= 120:
                        s += 1.0
                    else:
                        s -= min(3.0, diff / 300.0)
            if h.view_count:
                s += min(1.0, math.log10(max(1, h.view_count)) / 8.0)
            if h.like_count:
                s += min(0.5, h.like_count / 5000.0)
            return s

        ranked = sorted(hits, key=score, reverse=True)
        best = ranked[0]
        if score(best) < 2.0:
            logger.warning("weak hit for %r: %s", query, best.title)
        return best

    # --------------------------------------------------------------- download
    async def download_audio(
        self,
        video: VideoHit,
        audio_format: str,
        kbps: int,
        progress_cb: Optional[ProgressCb] = None,
    ) -> tuple:
        """دانلود + تبدیل به mp3/m4a → (مسیر فایل، حجم بایت)"""
        name = re.sub(r"[^\w\u0600-\u06FF]+", "_", video.title)[:80].strip("_") or "audio"
        base = os.path.join(self.work_dir, f"{name}~{video.yt_id}")
        out_tmpl = base + ".%(ext)s"

        merge_fmt = audio_format if audio_format == "m4a" else "mp3"
        cmd = [
            "yt-dlp",
            "-f", "ba/b",          # بهترین کیفیت صوتی
            "-x",
            "--audio-format", merge_fmt,
            "--audio-quality", str(kbps),
            "--merge-output-format", merge_fmt,
            "--no-playlist",
            "--force-overwrites",
            "--no-simulate",
            "-o", out_tmpl,
            video.url,
        ]

        async with self._lock:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            last_pct = -1
            err_tail: List[str] = []
            try:
                while True:
                    line = await proc.stderr.readline()
                    if not line:
                        break
                    text = line.decode(errors="ignore").strip()
                    err_tail.append(text)
                    if len(err_tail) > 6:
                        err_tail.pop(0)
                    m = _PCT_RE.search(text)
                    if m:
                        pct = int(m.group(1))
                        if pct - last_pct >= 10 or pct >= 100:
                            last_pct = pct
                            if progress_cb:
                                try:
                                    await progress_cb(pct, text)
                                except Exception:  # noqa: BLE001
                                    pass
                await asyncio.wait_for(proc.wait(), timeout=300)
            except asyncio.TimeoutError:
                proc.kill()
                raise DownloadError("دانلود بیش از حد طول کشید؛ دوباره امتحان کن.")

            if proc.returncode != 0:
                tail = " ".join(err_tail)[-300:]
                logger.error("download failed: %s", tail)
                raise DownloadError(f"دانلود ناکام بود. {tail}")

        for ext in ("mp3", "m4a", "webm", "opus", "aac", "mp4"):
            p = f"{base}.{ext}"
            if os.path.isfile(p) and os.path.getsize(p) > 0:
                return p, os.path.getsize(p)
        raise DownloadError("فایل خروجی پیدا نشد (ممکن است ffmpeg مشکل داشته باشد).")
