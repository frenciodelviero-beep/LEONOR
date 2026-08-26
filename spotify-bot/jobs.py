"""
jobs.py — مدیریت سفارش‌های در انتظار (دکمه‌های شیشه‌ای + TTL)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from models import KIND_ALBUM, KIND_PLAYLIST, Track


@dataclass
class Job:
    """یک سفارش دانلود — تک‌آهنگ یا مجموعه (آلبوم/پلی‌لیست)"""

    job_id: str
    kind: str                 # track | album | playlist
    sp_id: str                # آیدی آیتم در اسپاتیفیا
    title: str
    tracks: List[Track]
    image_url: str = ""
    created_by: int = 0
    total_tracks: int = 0     # کل آهنگ‌های اصلی (قبل از truncation)
    status: str = "waiting"   # waiting | running | done | canceled | expired
    ts: float = field(default_factory=time.time)

    @property
    def is_collection(self) -> bool:
        return self.kind in (KIND_ALBUM, KIND_PLAYLIST)


class JobStore:
    """فهرست jobها در حافظه با پاک‌سازی خودکار"""

    def __init__(self, ttl_seconds: int = 900):
        self._jobs: Dict[str, Job] = {}
        self._ttl = ttl_seconds

    def add(self, job: Job) -> Job:
        self._purge()
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        job = self._jobs.get(job_id)
        if job and job.status == "waiting" and (time.time() - job.ts) > self._ttl:
            job.status = "expired"
        return job

    def _purge(self) -> None:
        now = time.time()
        stale = [k for k, v in self._jobs.items() if now - v.ts > self._ttl * 2]
        for k in stale:
            self._jobs.pop(k, None)
