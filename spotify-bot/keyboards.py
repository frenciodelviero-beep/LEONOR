"""
keyboards.py — سازنده‌های کیبورد inline
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils import to_fa

# کیفیت‌های قابل انتخاب: (kbps, فرمت)
QUALITIES = [
    (128, "mp3"),
    (192, "mp3"),
    (320, "mp3"),
    (192, "m4a"),
]


def quality_buttons(job_id: str, note: str = "") -> InlineKeyboardMarkup:
    """دکمه‌های انتخاب کیفیت برای یک job خاص"""
    b = InlineKeyboardBuilder()
    row = []
    for kbps, fmt in QUALITIES:
        label = f"{fmt.upper()} {to_fa(kbps)}"
        if note:
            label += f" • {note}"
        row.append(
            InlineKeyboardButton(text=label, callback_data=f"q:{job_id}:{kbps}:{fmt}")
        )
    b.row(*row)
    b.row(InlineKeyboardButton(text="❌ لغو", callback_data=f"x:{job_id}"))
    return b.as_markup()


def quality_picker() -> InlineKeyboardMarkup:
    """کیبورد دستور /quality — ذخیرهٔ کیفیت پیش‌فرض کاربر"""
    b = InlineKeyboardBuilder()
    for kbps, fmt in QUALITIES:
        b.button(text=f"{fmt.upper()} {to_fa(kbps)}", callback_data=f"setq:{kbps}:{fmt}")
    b.adjust(2)
    return b.as_markup()


def status_keyboard(text: str, emoji: str = "⏳") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=f"{emoji} {text}", disabled=True)]]
    )


def done_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ انجام شد", disabled=True)]]
    )
