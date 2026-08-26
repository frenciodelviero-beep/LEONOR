"""
handlers/links.py — ورودی اصلی: هر پیامی که لینک اسپاتیفای توشه
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import Message

from context import AppContext
from jobs import Job
from keyboards import quality_buttons
from models import KIND_ALBUM, KIND_PLAYLIST, KIND_TRACK, KIND_LABELS_FA
from spotify import SpotifyError
from utils import (
    bot_mentioned,
    clip,
    esc,
    format_duration,
    new_job_id,
    parse_spotify_url,
    to_fa,
)

logger = logging.getLogger("links")
router = Router(name="links")


async def _should_respond(message: Message) -> bool:
    """در چت خصوصی همیشه؛ در گروه فقط با ری‌پلای یا منشن"""
    if message.chat.type == "private":
        return True
    if message.reply_to_message is not None:
        return True
    return bot_mentioned(message.text, message.bot.username or "")


@router.message(F.text)
async def on_message(message: Message, ctx: AppContext) -> None:
    parsed = parse_spotify_url(message.text or "")
    if not parsed:
        return
    if not await _should_respond(message):
        return

    kind, sp_id = parsed

    ok, wait = ctx.cooldown.check(message.chat.id)
    if not ok:
        await message.answer(
            f"⏳ آروم باش! {to_fa(int(wait) + 1)} ثانیه دیگه امتحان کن (ضد اسپم)."
        )
        return

    busy = await message.answer(
        f"🛰️ دارم اطلاعات {KIND_LABELS_FA[kind]} رو از اسپاتیفای می‌کشم ..."
    )
    try:
        if kind == KIND_TRACK:
            track = await ctx.spotify.track(sp_id)
            job = ctx.jobs.add(
                Job(
                    job_id=new_job_id(),
                    kind=kind,
                    sp_id=sp_id,
                    title=track.short_info(),
                    tracks=[track],
                    image_url=track.image_url,
                    created_by=message.from_user.id or 0,
                )
            )
            ctx.cooldown.mark(message.chat.id)
            await _send_track_card(message, job, track)
        else:
            coll = await ctx.spotify.collection(kind, sp_id)
            cap = ctx.cfg.max_tracks_per_job
            job = ctx.jobs.add(
                Job(
                    job_id=new_job_id(),
                    kind=kind,
                    sp_id=coll.id,
                    title=coll.title,
                    tracks=coll.tracks[:cap],
                    image_url=coll.image_url,
                    created_by=message.from_user.id or 0,
                    total_tracks=coll.total,
                )
            )
            ctx.cooldown.mark(message.chat.id)
            await _send_collection_card(message, job, coll.total)
        try:
            await busy.delete()
        except Exception:  # noqa: BLE001
            pass
    except SpotifyError as e:
        logger.info("spotify error: %s", e)
        await busy.edit_text(f"😔 {e}")
    except Exception:  # noqa: BLE001
        logger.exception("unhandled error while resolving %r", message.text)
        await busy.edit_text("💥 یه خطای غیرمنتظره پیش اومد. یه کم دیگه امتحان کن.")


async def _send_track_card(message: Message, job: Job, track) -> None:
    album_line = (
        f"\n📀 <b>آلبوم:</b> {esc(clip(track.album, 40))}" if track.album else ""
    )
    text = (
        f"🎵 <b>{esc(clip(track.title, 60))}</b>\n"
        f"👤 {esc(clip(track.artist, 40))}{album_line}\n"
        f"⏱ {format_duration(track.duration_sec)}\n\n"
        "🔘 <b>کیفیت رو انتخاب کن:</b>"
    )
    await message.answer(
        text,
        reply_markup=quality_buttons(job.job_id),
        disable_web_page_preview=True,
    )


async def _send_collection_card(message: Message, job: Job, total: int) -> None:
    lines = [f"{KIND_LABELS_FA[job.kind]}: <b>{esc(clip(job.title, 50))}</b>"]
    listed = job.tracks[:8]
    for i, t in enumerate(listed, 1):
        lines.append(f"{to_fa(i)}. {esc(clip(t.title, 40))} — {esc(clip(t.artist, 30))}")
    if len(job.tracks) > len(listed):
        lines.append(f"… و {to_fa(len(job.tracks) - len(listed))} آهنگ دیگه")
    if total > len(job.tracks):
        lines.append(
            f"(⚠️ از {to_fa(total)} آهنگ، {to_fa(len(job.tracks))} تا اولی دانلود می‌شود)"
        )
    lines.append("")
    lines.append(f"🔘 <b>کیفیت {to_fa(len(job.tracks))} آهنگ رو انتخاب کن:</b>")
    await message.answer(
        "\n".join(lines),
        reply_markup=quality_buttons(job.job_id, note=f"{to_fa(len(job.tracks))} آهنگ"),
        disable_web_page_preview=True,
    )
