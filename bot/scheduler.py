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

scheduler: AsyncIOScheduler = AsyncIOScheduler()
bot = Bot(token=BOT_TOKEN)

async def check_all_domains() -> None:
    """
    Periodically checks all domains for availability, SSL validity, and WHOIS expiration.
    Sends a Telegram notification to the user if any issue is detected.
    """
    async with SessionLocal() as session:
        result = await session.execute(Domain.__table__.select())
        domains = result.fetchall()

        for row in domains:  # type: Any
            domain = row.name
            user_id = row.user_id

            # Get user settings
            user_settings = await session.get(UserSettings, user_id)

            # fallback helper
            def get_value(domain_value, settings_value):
                return domain_value if domain_value is not None else settings_value

            try:
                problems = []

                # HTTP/HTTPS availability checks
                if get_value(row.track_http, user_settings.track_http):
                    http_result = await check_http_https(domain)
                    if http_result.get("http", {}).get("status") != "ok":
                        problems.append(f"HTTP ❌ ({http_result['http'].get('error', 'error')})")
                if get_value(row.track_https, user_settings.track_https):
                    http_result = http_result if "http_result" in locals() else await check_http_https(domain)
                    if http_result.get("https", {}).get("status") != "ok":
                        problems.append(f"HTTPS ❌ ({http_result['https'].get('error', 'error')})")

                # SSL certificate checks
                if get_value(row.track_ssl, user_settings.track_ssl):
                    ssl_result = await check_ssl(domain)
                    ssl_days = get_value(row.ssl_warn_days, user_settings.ssl_warn_days)
                    if not ssl_result["valid"] or ssl_result.get("days_left", 0) < ssl_days:
                        problems.append("SSL certificate is expiring or invalid ⚠️")

                # WHOIS/domain expiration checks
                if get_value(row.track_whois, user_settings.track_whois):
                    whois_result = await check_domain_expiry(domain)
                    whois_days = get_value(row.whois_warn_days, user_settings.whois_warn_days)
                    if not whois_result["valid"] or whois_result.get("days_left", 0) < whois_days:
                        problems.append("Domain registration is expiring ⚠️")

                # Send notification if any issues detected
                if problems:
                    text = f"🚨 Issues detected for domain <b>{domain}</b>:\n" + "\n".join(f"• {p}" for p in problems)
                    await bot.send_message(user_id, text)
            except Exception as e:
                await bot.send_message(user_id, f"❌ Error occurred while checking {domain}: {str(e)}")