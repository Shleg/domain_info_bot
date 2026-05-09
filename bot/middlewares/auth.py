"""Restrict bot access to ``ALLOWED_USER_IDS``."""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import ALLOWED_USER_IDS


def _is_donate_command(message: Message) -> bool:
    if not message.text or not message.text.strip():
        return False
    cmd = message.text.strip().split()[0]
    base = cmd.split("@", 1)[0]
    return base == "/donate"


class AuthorizedUserMiddleware(BaseMiddleware):
    """
    Drops unauthorized updates centrally.
    ``/donate`` for outsiders is ignored silently (historical behaviour).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        uid: int | None = None

        if isinstance(event, Message) and event.from_user:
            uid = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            uid = event.from_user.id

        if uid is None:
            return await handler(event, data)

        if uid in ALLOWED_USER_IDS:
            return await handler(event, data)

        if isinstance(event, Message):
            if _is_donate_command(event):
                return None
            await event.answer("⛔️ You do not have access to this command.")
            return None

        if isinstance(event, CallbackQuery):
            await event.answer("⛔️ Not allowed", show_alert=True)

        return None
