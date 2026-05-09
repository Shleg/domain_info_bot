import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from config import BOT_TOKEN, CHECK_INTERVAL_MIN, SSL_CRON_HOUR, SSL_CRON_MINUTE
from bot.middlewares.auth import AuthorizedUserMiddleware
from bot.handlers.router import build_root_router
from bot.scheduler import (
    scheduler,
    check_http_https_domains,
    check_ssl_whois_domains,
    set_bot,
)
from db.db import init_db

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()
dp.message.middleware(AuthorizedUserMiddleware())
dp.callback_query.middleware(AuthorizedUserMiddleware())
dp.include_router(build_root_router())


async def main() -> None:
    await bot.delete_my_commands()
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Start the bot"),
            BotCommand(command="list", description="List all domains"),
            BotCommand(
                command="settings",
                description="Show or edit monitoring settings",
            ),
            BotCommand(command="donate", description="Support the project via PayPal"),
            BotCommand(command="help", description="Help with commands"),
        ]
    )
    await init_db()
    set_bot(bot)
    scheduler.add_job(
        check_http_https_domains,
        "interval",
        minutes=CHECK_INTERVAL_MIN,
    )
    scheduler.add_job(
        check_ssl_whois_domains,
        "cron",
        hour=SSL_CRON_HOUR,
        minute=SSL_CRON_MINUTE,
    )
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
