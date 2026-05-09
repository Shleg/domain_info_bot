from aiogram import Router, F
from aiogram.types import CallbackQuery

from db.db import SessionLocal
from db.models import UserSettings
from db.repositories import get_domain

settings_router = Router()

TOGGLE_FIELDS = frozenset(
    {"track_http", "track_https", "track_ssl", "track_whois"}
)


@settings_router.callback_query(F.data.startswith("toggle:"))
async def toggle_setting_handler(callback: CallbackQuery):
    """
    Handler for inline button toggles to enable/disable monitoring settings.

    Format of callback_data:
        toggle:global:track_ssl
        toggle:domain:example.com:track_http
    """
    parts = callback.data.split(":")
    scope = parts[1]

    if scope == "global":
        if len(parts) != 3:
            await callback.answer("Invalid toggle request")
            return
        setting_name = parts[2]
    elif scope == "domain":
        if len(parts) != 4:
            await callback.answer("Invalid toggle request")
            return
        domain_name = parts[2]
        setting_name = parts[3]
    else:
        await callback.answer("Invalid toggle request")
        return

    if setting_name not in TOGGLE_FIELDS:
        await callback.answer("Invalid toggle request")
        return

    async with SessionLocal() as session:
        if scope == "global":
            settings = await session.get(UserSettings, callback.from_user.id)
            if not settings:
                settings = UserSettings(user_id=callback.from_user.id)
                session.add(settings)
                await session.commit()
            current = getattr(settings, setting_name)
            setattr(settings, setting_name, not current)
            await session.commit()
            await callback.answer(
                f"{setting_name} set to {'ON' if not current else 'OFF'}"
            )
            await callback.message.delete()
            await callback.message.bot.send_message(
                callback.from_user.id, "/settings"
            )

        else:
            domain_obj = await get_domain(
                session, user_id=callback.from_user.id, name=domain_name
            )
            if domain_obj is None:
                await callback.answer("Domain not found")
                return

            current = getattr(domain_obj, setting_name)
            setattr(domain_obj, setting_name, not current)
            await session.commit()
            await callback.answer(
                f"{domain_name} {setting_name} set to {'ON' if not current else 'OFF'}"
            )
            await callback.message.delete()
            await callback.message.bot.send_message(
                callback.from_user.id, f"/settings {domain_name}"
            )
