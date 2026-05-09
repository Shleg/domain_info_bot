"""
Scheduler logic for periodic domain checks.

Includes:
- HTTP/HTTPS availability check
- SSL certificate monitoring
- Domain registration expiry monitoring
- Telegram notifications for failures or expiring resources
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime
from typing import Any

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.utils import check_domain_expiry, check_http_https, check_ssl
from db.db import SessionLocal
from db.models import Domain, UserSettings
from db.repositories import list_all_domains
from services.monitoring import (
    resolve_effective_settings,
    should_alert_availability,
    should_alert_expiry,
)

scheduler: AsyncIOScheduler = AsyncIOScheduler()

_bot_instance: Bot | None = None


def set_bot(bot: Bot) -> None:
    """Must be called from ``main`` before jobs run (single Bot instance app-wide)."""
    global _bot_instance
    _bot_instance = bot


def get_bot() -> Bot:
    if _bot_instance is None:
        raise RuntimeError(
            "Scheduler bot not configured: call set_bot() before starting jobs"
        )
    return _bot_instance


def _alert_signature(lines: list[str]) -> str:
    return "|".join(lines)


async def _finalize_availability_alert(
    *,
    domain_id: int,
    user_id: int,
    domain_name: str,
    problems: list[str],
) -> None:
    """Persist probe state; notify only when the issue set changed from the last alert."""
    sig = _alert_signature(problems) if problems else ""
    duplicate = False

    async with SessionLocal() as db:
        row = await db.get(Domain, domain_id)
        if row is None:
            return
        row.last_avail_check_at = datetime.utcnow()
        row.last_avail_ok = not bool(problems)
        duplicate = bool(problems) and row.last_avail_alert_signature == sig
        if not problems:
            row.last_avail_alert_signature = None
            row.last_avail_alert_at = None
        await db.commit()

    if not problems or duplicate:
        return

    text = (
        f"🚨 Availability issues for domain <b>{domain_name}</b>:\n"
        + "\n".join(f"• {p}" for p in problems)
    )
    await get_bot().send_message(user_id, text)

    async with SessionLocal() as db:
        row = await db.get(Domain, domain_id)
        if row:
            row.last_avail_alert_signature = sig
            row.last_avail_alert_at = datetime.utcnow()
            await db.commit()


async def _finalize_expiry_alert(
    *,
    domain_id: int,
    user_id: int,
    domain_name: str,
    problems: list[str],
) -> None:
    sig = _alert_signature(problems) if problems else ""
    duplicate = False

    async with SessionLocal() as db:
        row = await db.get(Domain, domain_id)
        if row is None:
            return
        row.last_expiry_check_at = datetime.utcnow()
        row.last_expiry_ok = not bool(problems)
        duplicate = bool(problems) and row.last_expiry_alert_signature == sig
        if not problems:
            row.last_expiry_alert_signature = None
            row.last_expiry_alert_at = None
        await db.commit()

    if not problems or duplicate:
        return

    text = (
        f"🚨 Expiry issues for domain <b>{domain_name}</b>:\n"
        + "\n".join(f"• {p}" for p in problems)
    )
    await get_bot().send_message(user_id, text)

    async with SessionLocal() as db:
        row = await db.get(Domain, domain_id)
        if row:
            row.last_expiry_alert_signature = sig
            row.last_expiry_alert_at = datetime.utcnow()
            await db.commit()


async def check_http_https_domains() -> None:
    semaphore = asyncio.Semaphore(5)
    async with SessionLocal() as session:
        rows = await list_all_domains(session)
        for d in rows:
            session.expunge(d)

    async def check_one(domain: Domain) -> None:
        async with SessionLocal() as settings_session:
            user_settings = await settings_session.get(
                UserSettings, domain.user_id
            )

        effective = resolve_effective_settings(domain, user_settings)

        await asyncio.sleep(random.uniform(1, 2))  # jitter delay
        async with semaphore:
            problems: list[str] = []
            try:
                http_result = (
                    await check_http_https(domain.name)
                    if effective.track_http or effective.track_https
                    else None
                )
                problems = should_alert_availability(http_result, effective)
            except Exception as e:
                problems = [
                    f"❌ Error checking HTTP/HTTPS for {domain.name}: {str(e)}"
                ]

            await _finalize_availability_alert(
                domain_id=domain.id,
                user_id=domain.user_id,
                domain_name=domain.name,
                problems=problems,
            )

    await asyncio.gather(*(check_one(row) for row in rows))


async def check_ssl_whois_domains() -> None:
    async with SessionLocal() as session:
        domains = await list_all_domains(session)
        for d in domains:
            session.expunge(d)

    for domain in domains:  # type: Any
        async with SessionLocal() as session:
            user_settings = await session.get(UserSettings, domain.user_id)
        effective = resolve_effective_settings(domain, user_settings)

        problems: list[str] = []
        try:
            ssl_result = await check_ssl(domain.name) if effective.track_ssl else None
            whois_result = (
                await check_domain_expiry(domain.name)
                if effective.track_whois
                else None
            )
            problems = should_alert_expiry(ssl_result, whois_result, effective)
        except Exception as e:
            problems = [
                f"❌ Error checking SSL/WHOIS for {domain.name}: {str(e)}"
            ]

        await _finalize_expiry_alert(
            domain_id=domain.id,
            user_id=domain.user_id,
            domain_name=domain.name,
            problems=problems,
        )
