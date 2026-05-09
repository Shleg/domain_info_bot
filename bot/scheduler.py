"""
Scheduler logic for periodic domain checks.

Includes:
- HTTP/HTTPS availability check
- SSL certificate monitoring
- Domain registration expiry monitoring
- Telegram notifications for failures or expiring resources
"""

from typing import Any

import asyncio
import random

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from db.db import SessionLocal
from db.models import Domain, UserSettings
from services.monitoring import (
    resolve_effective_settings,
    should_alert_availability,
    should_alert_expiry,
)
from bot.utils import check_http_https, check_ssl, check_domain_expiry

scheduler: AsyncIOScheduler = AsyncIOScheduler()

_bot_instance: Bot | None = None


def set_bot(bot: Bot) -> None:
    """Must be called from ``main`` before jobs run (single Bot instance app-wide)."""
    global _bot_instance
    _bot_instance = bot


def get_bot() -> Bot:
    if _bot_instance is None:
        raise RuntimeError("Scheduler bot not configured: call set_bot() before starting jobs")
    return _bot_instance


async def check_http_https_domains() -> None:
    semaphore = asyncio.Semaphore(5)
    async with SessionLocal() as session:
        result = await session.execute(Domain.__table__.select())
        rows = result.fetchall()

    async def check_one(
        domain: str,
        user_id: int,
        row: Any,
    ) -> None:
        async with SessionLocal() as settings_session:
            user_settings = await settings_session.get(UserSettings, user_id)

        effective = resolve_effective_settings(row, user_settings)

        await asyncio.sleep(random.uniform(1, 2))  # jitter delay
        async with semaphore:
            try:
                http_result = (
                    await check_http_https(domain)
                    if effective.track_http or effective.track_https
                    else None
                )
                problems = should_alert_availability(http_result, effective)
                if problems:
                    text = (
                        f"🚨 Availability issues for domain <b>{domain}</b>:\n"
                        + "\n".join(f"• {p}" for p in problems)
                    )
                    await get_bot().send_message(user_id, text)
            except Exception as e:
                await get_bot().send_message(
                    user_id, f"❌ Error checking HTTP/HTTPS for {domain}: {str(e)}"
                )

    await asyncio.gather(*(check_one(r.name, r.user_id, r) for r in rows))


async def check_ssl_whois_domains() -> None:
    bot = get_bot()
    async with SessionLocal() as session:
        result = await session.execute(Domain.__table__.select())
        domains = result.fetchall()

        for row in domains:  # type: Any
            domain = row.name
            user_id = row.user_id
            user_settings = await session.get(UserSettings, user_id)
            effective = resolve_effective_settings(row, user_settings)

            try:
                ssl_result = await check_ssl(domain) if effective.track_ssl else None
                whois_result = (
                    await check_domain_expiry(domain) if effective.track_whois else None
                )
                problems = should_alert_expiry(ssl_result, whois_result, effective)

                if problems:
                    text = (
                        f"🚨 Expiry issues for domain <b>{domain}</b>:\n"
                        + "\n".join(f"• {p}" for p in problems)
                    )
                    await bot.send_message(user_id, text)
            except Exception as e:
                await bot.send_message(
                    user_id, f"❌ Error checking SSL/WHOIS for {domain}: {str(e)}"
                )
