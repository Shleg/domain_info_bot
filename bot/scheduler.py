"""
Scheduler logic for periodic domain checks.

Includes:
- HTTP/HTTPS availability check
- SSL certificate monitoring
- Domain registration expiry monitoring
- Telegram notifications for failures or expiring resources
"""
from typing import Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db.db import SessionLocal
from db.models import Domain, UserSettings
from bot.utils import check_http_https, check_ssl, check_domain_expiry
from aiogram import Bot
from config import BOT_TOKEN
import random
import asyncio

scheduler: AsyncIOScheduler = AsyncIOScheduler()
bot = Bot(token=BOT_TOKEN)

def get_value(domain_value, settings_value):
    return domain_value if domain_value is not None else settings_value


async def check_http_https_domains() -> None:
    semaphore = asyncio.Semaphore(5)
    async with SessionLocal() as session:
        result = await session.execute(Domain.__table__.select())
        rows = result.fetchall()

    async def check_one(
        domain: str,
        user_id: int,
        row_track_http: bool | None,
        row_track_https: bool | None,
    ) -> None:
        async with SessionLocal() as settings_session:
            user_settings = await settings_session.get(UserSettings, user_id)
        track_http_on = row_track_http if row_track_http is not None else (
            user_settings.track_http if user_settings is not None else True
        )
        track_https_on = row_track_https if row_track_https is not None else (
            user_settings.track_https if user_settings is not None else True
        )

        await asyncio.sleep(random.uniform(1, 2))  # jitter delay
        async with semaphore:
            try:
                problems: list[str] = []
                http_result = None
                if track_http_on or track_https_on:
                    http_result = await check_http_https(domain)
                if track_http_on and http_result is not None:
                    if http_result.get("http", {}).get("status") != "ok":
                        problems.append(
                            f"HTTP ❌ ({http_result['http'].get('error', 'error')})"
                        )
                if track_https_on and http_result is not None:
                    if http_result.get("https", {}).get("status") != "ok":
                        problems.append(
                            f"HTTPS ❌ ({http_result['https'].get('error', 'error')})"
                        )
                if problems:
                    text = (
                        f"🚨 Availability issues for domain <b>{domain}</b>:\n"
                        + "\n".join(f"• {p}" for p in problems)
                    )
                    await bot.send_message(user_id, text)
            except Exception as e:
                await bot.send_message(
                    user_id, f"❌ Error checking HTTP/HTTPS for {domain}: {str(e)}"
                )

    await asyncio.gather(
        *(check_one(r.name, r.user_id, r.track_http, r.track_https) for r in rows)
    )

async def check_ssl_whois_domains() -> None:
    async with SessionLocal() as session:
        result = await session.execute(Domain.__table__.select())
        domains = result.fetchall()

        for row in domains:  # type: Any
            domain = row.name
            user_id = row.user_id

            user_settings = await session.get(UserSettings, user_id)

            try:
                problems = []

                if get_value(row.track_ssl, user_settings.track_ssl if user_settings else True):
                    ssl_result = await check_ssl(domain)
                    ssl_days = get_value(row.ssl_warn_days, user_settings.ssl_warn_days if user_settings else 15)
                    if not ssl_result["valid"] or ssl_result.get("days_left", 0) < ssl_days:
                        problems.append("SSL certificate is expiring or invalid ⚠️")

                if get_value(row.track_whois, user_settings.track_whois if user_settings else True):
                    whois_result = await check_domain_expiry(domain)
                    whois_days = get_value(row.whois_warn_days, user_settings.whois_warn_days if user_settings else 30)
                    if not whois_result["valid"] or whois_result.get("days_left", 0) < whois_days:
                        problems.append("Domain registration is expiring ⚠️")

                if problems:
                    text = f"🚨 Expiry issues for domain <b>{domain}</b>:\n" + "\n".join(f"• {p}" for p in problems)
                    await bot.send_message(user_id, text)
            except Exception as e:
                await bot.send_message(user_id, f"❌ Error checking SSL/WHOIS for {domain}: {str(e)}")