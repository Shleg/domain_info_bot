from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import asyncio

from config import BOT_TOKEN
from db.db import init_db

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


# Хэндлер команды /start
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer("👋 Привет! Я слежу за сайтами. Отправь мне домен, чтобы добавить его в отслеживание.")


async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
