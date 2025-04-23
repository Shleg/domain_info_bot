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
from db.models import Domain
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
            try:
                # Check HTTP and HTTPS availability asynchronously
                http_result = await check_http_https(domain)
                # Check SSL certificate synchronously
                ssl_result = check_ssl(domain)
                # Check domain registration expiry synchronously
                whois_result = check_domain_expiry(domain)

                problems = []

                # HTTP/HTTPS availability checks
                for proto in ["http", "https"]:
                    if http_result.get(proto, {}).get("status") != "ok":
                        problems.append(f"{proto.upper()} ❌ ({http_result[proto].get('error', 'error')})")

                # SSL expiration and validity check
                if not ssl_result["valid"] or ssl_result.get("days_left", 0) < 30:
                    problems.append("SSL certificate is expiring or invalid ⚠️")

                # Domain registration expiry check
                if not whois_result["valid"] or whois_result.get("days_left", 0) < 30:
                    problems.append("Domain registration is expiring ⚠️")

                # Send notification if any issues detected
                if problems:
                    text = f"🚨 Issues detected for domain <b>{domain}</b>:\n" + "\n".join(f"• {p}" for p in problems)
                    await bot.send_message(user_id, text)
            except Exception as e:
                # General error during domain checking
                await bot.send_message(user_id, f"❌ Error occurred while checking {domain}: {str(e)}")