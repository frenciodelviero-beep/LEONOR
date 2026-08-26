"""
handlers/errors.py — catch-all خطاها: لاگ کامل + پیام مهربانانه به کاربر
"""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import ErrorEvent

logger = logging.getLogger("errors")
router = Router(name="errors")


@router.errors()
async def on_error(event: ErrorEvent) -> None:
    logger.exception("error", exc_info=event.exception)
    update = event.update
    try:
        if update is None:
            return
        if update.message is not None:
            await update.message.answer("💥 خطایی پیش اومد. یه کم دیگه امتحان کن.")
        elif update.callback_query is not None:
            await update.callback_query.answer("خطا! دوباره امتحان کن.", show_alert=True)
    except Exception:  # noqa: BLE001
        pass
