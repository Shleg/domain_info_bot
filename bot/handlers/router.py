"""Root router assembling command, callback and settings subgraphs."""
from aiogram import Router

from bot.handlers.callbacks import callbacks_router
from bot.handlers.commands import commands_router
from bot.handlers.settings import settings_router


def build_root_router() -> Router:
    root = Router()
    root.include_router(settings_router)
    root.include_router(callbacks_router)
    root.include_router(commands_router)
    return root
