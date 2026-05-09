"""Shared manual domain check (/check command and inline button)."""
from typing import Union

from aiogram.types import CallbackQuery, Message

from db.db import SessionLocal
from db.repositories import ensure_user_settings, get_domain
from services.monitoring import (
    resolve_effective_settings,
    run_full_check,
    format_check_report_message,
)


async def perform_check(source: Union[Message, CallbackQuery], domain: str) -> None:
    if isinstance(source, CallbackQuery):
        user_id = source.from_user.id
        message = source.message
        if message is None:
            await source.answer("⚠️ Unable to show results here.", show_alert=True)
            return
    else:
        user_id = source.from_user.id
        message = source

    await message.answer(f"🔍 Checking <b>{domain}</b>...")

    async with SessionLocal() as session:
        domain_row = await get_domain(session, user_id=user_id, name=domain)
        settings = await ensure_user_settings(session, user_id)

    effective = resolve_effective_settings(domain_row, settings)
    report = await run_full_check(domain, effective)
    reply = format_check_report_message(domain, report, effective)
    await message.answer(reply)
