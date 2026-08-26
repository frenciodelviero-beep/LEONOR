"""
handlers/callbacks.py — دکمه‌های شیشه‌ای: انتخاب کیفیت، شروع دانلود، لغو
"""
from __future__ import annotations

import logging
import os

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from context import AppContext
from downloader import DownloadError
from jobs import Job
from keyboards import done_keyboard, quality_buttons, status_keyboard
from utils import clip, esc, human_size, progress_bar, safe_filename, to_fa

logger = logging.getLogger("callbacks")
router = Router(name="callbacks")


def _unlink(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


async def _safe_edit(message: Message, text: str) -> None:
    """edit با fallback روی answer (اگر پیام پاک/ویرایش‌شده باشد)"""
    try:
        await message.edit_text(text)
    except Exception:  # noqa: BLE001
        try:
            await message.answer(text)
        except Exception:  # noqa: BLE001
            pass


async def _finish_card(message: Message, job: Job) -> None:
    job.status = "done"
    try:
        await message.edit_reply_keyboard(reply_keyboard=done_keyboard())
    except Exception:  # noqa: BLE001
        pass


# ------------------------------------------------------------ تنظیم کیفیت
@router.callback_query(F.data & F.data.startswith("setq:"))
async def cb_set_quality(call: CallbackQuery, ctx: AppContext) -> None:
    _, kbps, _fmt = call.data.split(":")
    await ctx.settings.set_quality(call.from_user.id, int(kbps))
    await call.message.edit_text(
        f"✅ کیفیت پیش‌فرض: <b>{to_fa(kbps)} kbps</b>\n"
        "هر وقت لینکی بفرستی، این کیفیت اعمال می‌شه."
    )
    await call.answer("ذخیره شد!")


# ------------------------------------------------------------------- لغو
@router.callback_query(F.data & F.data.startswith("x:"))
async def cb_cancel(call: CallbackQuery, ctx: AppContext) -> None:
    job = ctx.jobs.get(call.data.split(":", 1)[1])
    if job and job.status == "waiting":
        job.status = "canceled"
        try:
            await call.message.edit_reply_keyboard(reply_keyboard=done_keyboard())
        except Exception:  # noqa: BLE001
            pass
        await call.answer("لغو شد.")
    else:
        await call.answer("این دکمه دیگه در دسترس نیست.", show_alert=True)


# ------------------------------------------------------------- شروع دانلود
@router.callback_query(F.data & F.data.startswith("q:"))
async def cb_quality(call: CallbackQuery, ctx: AppContext) -> None:
    _, job_id, kbps, fmt = call.data.split(":")
    job = ctx.jobs.get(job_id)
    if job is None:
        await call.answer("این دکمه دیگه معتبر نیست — دوباره لینک بفرست.", show_alert=True)
        return
    if job.status == "running":
        await call.answer("⏳ این کار در حال انجام است ...", show_alert=True)
        return
    if job.status != "waiting":
        await call.answer("این دکمه دیگه معتبر نیست — دوباره لینک بفرست.", show_alert=True)
        return

    job.status = "running"
    try:
        await call.message.edit_reply_keyboard(
            reply_keyboard=status_keyboard("در حال آماده‌سازی ...")
        )
    except Exception:  # noqa: BLE001
        pass
    await call.answer("شروع شد 🚀")
    ctx.spawn(_run_job(call.message, ctx, job, int(kbps), fmt))


async def _run_job(message: Message, ctx: AppContext, job: Job, kbps: int, fmt: str) -> None:
    try:
        if job.is_collection:
            await _run_collection(message, ctx, job, kbps, fmt)
        else:
            await _run_single(message, ctx, job, kbps, fmt)
    except Exception:  # noqa: BLE001
        logger.exception("job %s crashed", job.job_id)
        await _safe_edit(message, "💥 خطای غیرمنتظره پیش اومد. دوباره امتحان کن.")


# ---------------------------------------------------------------- تک‌آهنگ
async def _run_single(message: Message, ctx: AppContext, job: Job, kbps: int, fmt: str) -> None:
    track = job.tracks[0]
    fmt_label = f"{fmt.upper()} {to_fa(kbps)}"
    limit_bytes = ctx.cfg.telegram_file_limit_mb * 1024 * 1024

    status = await message.answer(
        f"🔍 در یوتیوب جستجو می‌کنم: <b>{esc(clip(track.query, 70))}</b> ..."
    )

    try:
        hit = await ctx.dl.search_youtube(track.query, target_duration=track.duration_sec or None)
    except DownloadError as e:
        await _safe_edit(status, f"😕 {e}")
        return
    if hit is None:
        await _safe_edit(
            status,
            "😕 هیچ نتیجه‌ای در یوتیوب پیدا نشد.\n"
            "اگه آهنگ تازه‌ست یا کم‌بینواست، یه کم دیگه امتحان کن.",
        )
        return

    async def on_progress(pct: int, _raw: str) -> None:
        await _safe_edit(
            status,
            f"⬇️ در حال دانلود ({fmt_label})\n{progress_bar(pct)} <b>{to_fa(pct)}٪</b>",
        )

    await _safe_edit(status, f"⬇️ در حال دانلود ({fmt_label})\n{progress_bar(0)} <b>شروع شد</b>")

    try:
        path, size = await ctx.dl.download_audio(hit, fmt, kbps, progress_cb=on_progress)
    except DownloadError as e:
        await _safe_edit(status, f"😖 {e}")
        await ctx.stats.record(job.kind, ok=False, user_id=job.created_by)
        return

    if size > limit_bytes:
        _unlink(path)
        await _safe_edit(
            status,
            f"📦 فایل {human_size(size)} شد و از سقف "
            f"{to_fa(ctx.cfg.telegram_file_limit_mb)}MB تلگرام رد شده.\n"
            "کیفیت پایین‌تر رو انتخاب کن.",
        )
        job.status = "waiting"
        try:
            await message.edit_reply_keyboard(reply_keyboard=quality_buttons(job.job_id))
        except Exception:  # noqa: BLE001
            pass
        return

    await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_AUDIO)
    filename = f"{safe_filename(track.title, 40)} - {safe_filename(track.artist, 30)}.{fmt}"
    caption = (
        f"🎵 <b>{esc(clip(track.title, 60))}</b>\n"
        f"👤 {esc(clip(track.artist, 40))}\n"
        f"🎚 {fmt_label} • {human_size(size)}"
    )
    with open(path, "rb") as f:
        await message.answer_audio(
            audio=BufferedInputFile(f.read(), filename=filename),
            caption=caption,
            title=clip(track.title, 100),
            performer=clip(track.artist, 100),
            duration=track.duration_sec or None,
        )
    _unlink(path)

    await _finish_card(message, job)
    await _safe_edit(status, f"✅ آماده شد! ({human_size(size)})")
    await ctx.stats.record(job.kind, ok=True, n_tracks=1, nbytes=size, user_id=job.created_by)


# -------------------------------------------------------------- مجموعه
async def _run_collection(message: Message, ctx: AppContext, job: Job, kbps: int, fmt: str) -> None:
    n = len(job.tracks)
    fmt_label = f"{fmt.upper()} {to_fa(kbps)}"
    limit_bytes = ctx.cfg.telegram_file_limit_mb * 1024 * 1024

    status = await message.answer(
        f"🚀 دانلود {to_fa(n)} آهنگ از «<b>{esc(clip(job.title, 40))}</b>» شروع شد ... ({fmt_label})"
    )
    ok_count = 0
    total_bytes = 0

    for i, track in enumerate(job.tracks, 1):
        line = (
            f"🎵 <b>{to_fa(i)}/{to_fa(n)}</b> — {esc(clip(track.title, 40))} "
            f"({esc(clip(track.artist, 25))})"
        )
        await _safe_edit(status, line)
        try:
            hit = await ctx.dl.search_youtube(
                track.query, target_duration=track.duration_sec or None
            )
            if hit is None:
                await _safe_edit(status, line + "\n❌ نتیجه‌ای پیدا نشد؛ رد می‌شم.")
                continue

            async def on_progress(pct: int, _raw: str, _st=status, _line=line) -> None:
                await _safe_edit(_st, _line + f"\n{progress_bar(pct)} <b>{to_fa(pct)}٪</b>")

            path, size = await ctx.dl.download_audio(hit, fmt, kbps, progress_cb=on_progress)

            if size > limit_bytes:
                _unlink(path)
                await _safe_edit(
                    status,
                    line + f"\n⚠️ فایل {human_size(size)} شد و از سقف تلگرام رد شد؛ رد می‌شم.",
                )
                continue

            await message.bot.send_chat_action(message.chat.id, ChatAction.SEND_DOCUMENT)
            filename = (
                f"{to_fa(i)} - {safe_filename(track.title, 40)} - "
                f"{safe_filename(track.artist, 25)}.{fmt}"
            )
            caption = (
                f"({to_fa(i)}/{to_fa(n)}) 🎵 <b>{esc(clip(track.title, 50))}</b>\n"
                f"👤 {esc(clip(track.artist, 35))}\n"
                f"🎚 {fmt_label} • {human_size(size)}"
            )
            with open(path, "rb") as f:
                await message.answer_audio(
                    audio=BufferedInputFile(f.read(), filename=filename),
                    caption=caption,
                    title=clip(track.title, 100),
                    performer=clip(track.artist, 100),
                )
            _unlink(path)
            ok_count += 1
            total_bytes += size
            await _safe_edit(status, line + f"\n✅ ارسال شد ({human_size(size)})")
        except DownloadError as e:
            logger.warning("track failed (%s): %s", track.title, e)
            await _safe_edit(status, line + f"\n❌ {esc(clip(str(e), 80))} — رد می‌شم")
        except Exception:  # noqa: BLE001
            logger.exception("unexpected error on track %s", track.title)
            await _safe_edit(status, line + "\n❌ خطای غیرمنتظره — رد می‌شم")

    await _safe_edit(
        status,
        "🎉 تمام شد!\n"
        f"✅ موفق: <b>{to_fa(ok_count)}/{to_fa(n)}</b>\n"
        f"💾 حجم کل: <b>{human_size(total_bytes)}</b>\n"
        f"🎚 {fmt_label}",
    )
    await _finish_card(message, job)
    await ctx.stats.record(
        job.kind,
        ok=ok_count > 0,
        n_tracks=ok_count,
        nbytes=total_bytes,
        user_id=job.created_by,
    )
