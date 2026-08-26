"""
context.py — کانتکست مشترک همهٔ هندلرها (از طریق workflow data dispatcher تزریق می‌شود)
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Coroutine, Set

import aiohttp
from aiogram import Bot

from config import Config
from downloader import Downloader
from jobs import JobStore
from spotify import SpotifyService
from store import Stats, UserSettings
from utils import ChatCooldown


@dataclass
class AppContext:
    cfg: Config
    bot: Bot
    http: aiohttp.ClientSession
    spotify: SpotifyService
    dl: Downloader
    stats: Stats
    settings: UserSettings
    jobs: JobStore
    cooldown: ChatCooldown
    bg_tasks: Set[asyncio.Task] = field(default_factory=set)

    def spawn(self, coro: Coroutine) -> asyncio.Task:
        """اجرای پس‌زمینه‌ای با نگه‌داشتن ارجاع تا task زامبی نشود"""
        task = asyncio.create_task(coro)
        self.bg_tasks.add(task)
        task.add_done_callback(self.bg_tasks.discard)
        return task

    async def close(self) -> None:
        for t in list(self.bg_tasks):
            t.cancel()
        await self.http.close()
