from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import asyncio

from config import BOT_TOKEN
from db.db import init_db
from db.models import Domain
from db.db import SessionLocal
from bot.utils import is_valid_domain

from config import ALLOWED_USER_IDS

def is_authorized(user_id: int) -> bool:
    return user_id in ALLOWED_USER_IDS

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


# Хэндлер команды /start
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("⛔️ У вас нет доступа к этой команде.")
        return

    await message.answer("👋 Привет! Я слежу за сайтами. Отправь мне домен, чтобы добавить его в отслеживание.")


@dp.message(F.text.startswith("/add"))
async def add_domain_handler(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("⛔️ У вас нет доступа к этой команде.")
        return

    parts = message.text.strip().split()

    if len(parts) != 2:
        await message.answer("⚠️ Правильное использование: <code>/add example.com</code>")
        return

    domain = parts[1].strip().lower()

    if not is_valid_domain(domain):
        await message.answer("❌ Это не похоже на валидное доменное имя.")
        return

    async with SessionLocal() as session:
        # Проверка, есть ли уже такой домен
        existing = await session.execute(
            Domain.__table__.select().where(Domain.name == domain)
        )
        result = existing.fetchone()

        if result:
            await message.answer("ℹ️ Этот домен уже отслеживается.")
            return

        # Создаём новый объект
        new_domain = Domain(
            name=domain,
            user_id=message.from_user.id
        )

        session.add(new_domain)
        await session.commit()

        await message.answer(f"✅ Домен <b>{domain}</b> добавлен в отслеживание.")


@dp.message(F.text == "/list")
async def list_domains_handler(message: Message):
    async with SessionLocal() as session:
        if not is_authorized(message.from_user.id):
            await message.answer("⛔️ У вас нет доступа к этой команде.")
            return

        result = await session.execute(Domain.__table__.select())
        domains = result.fetchall()

        if not domains:
            await message.answer("🔍 В базе пока нет доменов.")
            return

        text = "📝 Список отслеживаемых доменов:\n"
        for row in domains:
            text += f"• {row.name}\n"

        await message.answer(text)


async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
