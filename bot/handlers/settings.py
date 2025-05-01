

from aiogram import Router, F
from aiogram.types import CallbackQuery
from db.db import SessionLocal
from db.models import Domain, UserSettings

settings_router = Router()


@settings_router.callback_query(F.data.startswith("toggle:"))
async def toggle_setting_handler(callback: CallbackQuery):
    """
    Handler for inline button toggles to enable/disable monitoring settings.

    Format of callback_data:
        toggle:global:track_ssl
        toggle:domain:example.com:track_http
    """
    parts = callback.data.split(":")
    if len(parts) not in (3, 4):
        await callback.answer("Invalid toggle request")
        return

    scope = parts[1]
    async with SessionLocal() as session:
        if scope == "global":
            setting_name = parts[2]
            settings = await session.get(UserSettings, callback.from_user.id)
            if not settings:
                settings = UserSettings(user_id=callback.from_user.id)
                session.add(settings)
                await session.commit()
            current = getattr(settings, setting_name)
            setattr(settings, setting_name, not current)
            await session.commit()
            await callback.answer(f"{setting_name} set to {'ON' if not current else 'OFF'}")
            await callback.message.delete()
            await callback.message.bot.send_message(callback.from_user.id, "/settings")

        elif scope == "domain":
            domain_name = parts[2]
            setting_name = parts[3]
            domain_result = await session.execute(
                Domain.__table__.select().where(
                    Domain.name == domain_name,
                    Domain.user_id == callback.from_user.id
                )
            )
            domain = domain_result.fetchone()
            if not domain:
                await callback.answer("Domain not found")
                return

            current = getattr(domain, setting_name)
            setattr(domain, setting_name, not current)
            await session.execute(
                Domain.__table__.update()
                .where(Domain.id == domain.id)
                .values({setting_name: not current})
            )
            await session.commit()
            await callback.answer(f"{domain_name} {setting_name} set to {'ON' if not current else 'OFF'}")
            await callback.message.delete()
            await callback.message.bot.send_message(callback.from_user.id, f"/settings {domain_name}")