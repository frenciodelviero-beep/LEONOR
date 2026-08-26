"""
handlers/commands.py — دستورهای /start /help /quality /stats /ping
"""
from __future__ import annotations

import time

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from context import AppContext
from keyboards import quality_picker
from utils import to_fa

router = Router(name="commands")

WELCOME = (
    "🎧 <b>اسپاتی‌دانلودر</b> — رایگان، بی‌محدودیت، خفن!\n\n"
    "💡 <b>کار کردنش خیلی ساده‌ست:</b>\n"
    "لینک اسپاتیفای رو همین‌جا بفرست، من صداشو برات می‌دم:\n\n"
    "🎵 <code>open.spotify.com/track/...</code>\n"
    "💿 <code>open.spotify.com/album/...</code>\n"
    "📃 <code>open.spotify.com/playlist/...</code>\n\n"
    "👥 در <b>گروه‌ها</b> هم کار می‌کنم — فقط <code>@اسم_بات</code> رو توی پیام بنویس "
    "یا به پیامم <b>ری‌پلای</b> کن.\n\n"
    "⚙️ <b>دستورات</b>\n"
    "/quality — کیفیت پیش‌فرض دانلود\n"
    "/stats — آمار کلی\n"
    "/ping — سلامت سیستم\n"
    "/help — همین راهنما\n\n"
    "🔐 منبع صدا: جستجوی هوشمند در یوتیوب (yt-dlp) + تبدیل با ffmpeg\n"
    "⚖️ فقط برای استفادهٔ شخصی."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME, disable_web_page_preview=True)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(WELCOME, disable_web_page_preview=True)


@router.message(Command("ping"))
async def cmd_ping(message: Message) -> None:
    t0 = time.perf_counter()
    await message.bot.get_me()
    ms = int((time.perf_counter() - t0) * 1000)
    await message.answer(f"🏓 پینگ: <b>{to_fa(ms)}ms</b> — سیستم‌ها سبک و سالم 🟢")


@router.message(Command("stats"))
async def cmd_stats(message: Message, ctx: AppContext) -> None:
    await message.answer(await ctx.stats.summary())


@router.message(Command("quality"))
async def cmd_quality(message: Message, ctx: AppContext) -> None:
    cur = await ctx.settings.get_quality(
        message.from_user.id, ctx.cfg.default_quality_kbps
    )
    await message.answer(
        f"🎚 کیفیت فعلی شما: <b>{to_fa(cur)} kbps</b>\n"
        "یک کیفیت انتخاب کن تا پیش‌فرضت ذخیره بشه:",
        reply_markup=quality_picker(),
    )
