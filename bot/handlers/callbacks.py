"""Callback query handlers outside settings toggles."""
from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.handlers.check_execution import perform_check

callbacks_router = Router()


@callbacks_router.callback_query(F.data.startswith("check:"))
async def handle_check_callback(callback: CallbackQuery) -> None:
    domain = callback.data.split("check:", 1)[1]
    await perform_check(callback, domain)
    await callback.answer()


@callbacks_router.callback_query(F.data == "copy_crypto")
async def copy_crypto_handler(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.answer("Here is the wallet address 👇")
        await callback.message.answer(
            "<code>TUGi5pzSnM6kqpXMHkXiPL6yFyGmC9vAje</code>"
        )
    await callback.answer()
