from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db.db import SessionLocal
from db.models import Domain
from bot.utils import check_http_https, check_ssl, check_domain_expiry
from aiogram import Bot
from config import BOT_TOKEN

scheduler = AsyncIOScheduler()
bot = Bot(token=BOT_TOKEN)

async def check_all_domains():
    async with SessionLocal() as session:
        result = await session.execute(Domain.__table__.select())
        domains = result.fetchall()

        for row in domains:
            domain = row.name
            user_id = row.user_id
            try:
                http_result = await check_http_https(domain)
                ssl_result = check_ssl(domain)
                whois_result = check_domain_expiry(domain)

                problems = []

                # HTTP/HTTPS доступность
                for proto in ["http", "https"]:
                    if http_result.get(proto, {}).get("status") != "ok":
                        problems.append(f"{proto.upper()} ❌ ({http_result[proto].get('error', 'ошибка')})")

                # SSL
                if not ssl_result["valid"] or ssl_result.get("days_left", 0) < 30:
                    problems.append("SSL-сертификат ⚠️")

                # WHOIS
                if not whois_result["valid"] or whois_result.get("days_left", 0) < 30:
                    problems.append("Регистрация домена ⚠️")

                # Отправляем уведомление, если есть проблемы
                if problems:
                    text = f"🚨 Проблемы с доменом <b>{domain}</b>:\n" + "\n".join(f"• {p}" for p in problems)
                    await bot.send_message(user_id, text)
            except Exception as e:
                await bot.send_message(user_id, f"❌ Ошибка при проверке {domain}: {str(e)}")