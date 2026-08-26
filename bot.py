"""
bot.py — نقطهٔ ورود اسپاتی‌دانلودر 🎧

اجرا:  python bot.py
"""
from __future__ import annotations

import asyncio
import logging

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import load_config
from context import AppContext
from downloader import Downloader
from handlers import get_router
from jobs import JobStore
from spotify import SpotifyService
from store import Stats, UserSettings
from utils import ChatCooldown

log = logging.getLogger("main")


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)-12s | %(message)s",
        datefmt="%H:%M:%S",
    )


async def main() -> None:
    cfg = load_config()
    setup_logging(cfg.log_level)

    async with aiohttp.ClientSession() as http:
        bot = Bot(
            token=cfg.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        me = await bot.get_me()
        log.info("🤖 ربات %s (@%s) آماده‌ست", me.first_name, me.username)

        dl = Downloader(cfg.download_dir)
        spotify = SpotifyService(http, cfg.spotify_client_id, cfg.spotify_client_secret)
        if not cfg.spotify_api_enabled:
            log.warning(
                "⚠️ کلید Spotify API تنظیم نشده — فقط دانلود تک‌آهنگ فعال است "
                "(برای آلبوم/پلی‌لیست کلید بگذار)."
            )

        ctx = AppContext(
            cfg=cfg,
            bot=bot,
            http=http,
            spotify=spotify,
            dl=dl,
            stats=Stats("data/stats.json"),
            settings=UserSettings("data/settings.json"),
            jobs=JobStore(cfg.job_ttl_seconds),
            cooldown=ChatCooldown(cfg.rate_limit_seconds),
        )

        dp = Dispatcher(storage=MemoryStorage(), ctx=ctx)
        dp.include_router(get_router())

        await bot.set_my_commands(
            [
                BotCommand(command="start", description="شروع و راهنما"),
                BotCommand(command="help", description="راهنمای کامل"),
                BotCommand(command="quality", description="تنظیم کیفیت پیش‌فرض"),
                BotCommand(command="stats", description="آمار دانلودها"),
                BotCommand(command="ping", description="تست پینگ"),
            ]
        )

        log.info("🚀 polling شروع شد — لینک اسپاتیفای بفرست!")
        try:
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        finally:
            await ctx.close()
            await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 خداحافظ!")
