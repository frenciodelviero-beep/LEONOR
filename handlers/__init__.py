"""
handlers — مجموعهٔ routerها: دستورها، لینک‌های اسپاتیفای، دکمه‌ها و خطاها
"""
from __future__ import annotations

from aiogram import Router

from . import callbacks, commands, errors, links


def get_router() -> Router:
    r = Router(name="main")
    r.include_router(commands.router)
    r.include_router(links.router)
    r.include_router(callbacks.router)
    r.include_router(errors.router)
    return r
