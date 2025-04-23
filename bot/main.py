from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton

from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import asyncio

from config import BOT_TOKEN
from db.db import init_db
from db.models import Domain
from db.db import SessionLocal
from bot.utils import is_valid_domain, check_http_https, check_ssl, check_domain_expiry
from bot.scheduler import scheduler, check_all_domains

from config import ALLOWED_USER_IDS

def is_authorized(user_id: int) -> bool:
    """
    Check if the user ID is authorized to interact with the bot.

    Args:
        user_id (int): Telegram user ID.

    Returns:
        bool: True if authorized, False otherwise.
    """
    return user_id in ALLOWED_USER_IDS

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


# Handler for the /start command
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    """
    Handler for the /start command.
    Sends a greeting message to the authorized user.

    Args:
        message (Message): Telegram message object.
    """
    if not is_authorized(message.from_user.id):
        await message.answer("⛔️ You do not have access to this command.")
        return

    await message.answer("👋 Hi! I'm monitoring websites. Send me a domain to start monitoring it.")


@dp.message(F.text == "/help")
async def cmd_help(message: Message):
    """
    Handler for the /help command.
    Sends a help message with available commands to the authorized user.

    Args:
        message (Message): Telegram message object.
    """
    if not is_authorized(message.from_user.id):
        await message.answer("⛔️ You do not have access to this command.")
        return

    text = (
        "🤖 <b>Bot commands:</b>\n\n"
        "<b>/add example.com</b> — add a domain for monitoring\n"
        "<b>/remove example.com</b> — remove a domain from monitoring\n"
        "<b>/list</b> — show all monitored domains\n"
        "<b>/check example.com</b> — manually check a domain\n"
        "<b>/help</b> — show this help message"
    )
    await message.answer(text)




@dp.message(F.text.startswith("/add"))
async def add_domain_handler(message: Message):
    """
    Handler for the /add command.
    Adds a domain to the monitoring list for the authorized user.

    Args:
        message (Message): Telegram message object.
    """
    if not is_authorized(message.from_user.id):
        await message.answer("⛔️ You do not have access to this command.")
        return

    parts = message.text.strip().split()

    if len(parts) != 2:
        await message.answer("⚠️ Correct usage: <code>/add example.com</code>")
        return

    domain = parts[1].strip().lower()

    if not is_valid_domain(domain):
        await message.answer("❌ This does not look like a valid domain name.")
        return

    async with SessionLocal() as session:
        # Check if the domain is already monitored by this user
        existing = await session.execute(
            Domain.__table__.select().where(
                Domain.name == domain,
                Domain.user_id == message.from_user.id
            )
        )
        result = existing.fetchone()

        if result:
            await message.answer("ℹ️ This domain is already being monitored.")
            return

        # Create a new domain object
        new_domain = Domain(
            name=domain,
            user_id=message.from_user.id
        )

        session.add(new_domain)
        await session.commit()

        await message.answer(f"✅ Domain <b>{domain}</b> has been added for monitoring.")


@dp.message(F.text == "/list")
async def list_domains_handler(message: Message):
    """
    Handler for the /list command.
    Lists all domains being monitored by the authorized user.

    Args:
        message (Message): Telegram message object.
    """
    async with SessionLocal() as session:
        if not is_authorized(message.from_user.id):
            await message.answer("⛔️ You do not have access to this command.")
            return

        result = await session.execute(
            Domain.__table__.select().where(Domain.user_id == message.from_user.id)
        )
        domains = result.fetchall()

        if not domains:
            await message.answer("🔍 There are no domains in the database yet.")
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=row.name, callback_data=f"check:{row.name}")]
            for row in domains
        ])

        await message.answer("📝 Select a domain to check:", reply_markup=keyboard)



async def perform_check(message: Message, domain: str) -> None:
    """
    Performs a manual check of the specified domain's HTTP/HTTPS status, SSL certificate, and WHOIS info.

    Args:
        message (Message): Telegram message to reply to.
        domain (str): Domain name to check.
    """

    await message.answer(f"🔍 Checking <b>{domain}</b>...")

    results = await check_http_https(domain)

    reply = f"📊 Check results for <b>{domain}</b>:\n"
    for proto in ["http", "https"]:
        res = results.get(proto)
        if res["status"] == "ok":
            reply += f"• <b>{proto.upper()}</b>: ✅ {res['code']}\n"
        else:
            reply += f"• <b>{proto.upper()}</b>: ❌ {res['error']}\n"

    ssl_result = await check_ssl(domain)
    reply += "\n🔐 <b>SSL Certificate:</b>\n"
    if ssl_result["valid"]:
        reply += (
            f"• Issuer: {ssl_result['issuer']}\n"
            f"• Valid until: {ssl_result['expires_at']}\n"
            f"• Days left: {ssl_result['days_left']}\n"
        )
    else:
        reply += f"• ❌ SSL check error: {ssl_result['error']}\n"

    whois_result = await check_domain_expiry(domain)
    reply += "\n🌐 <b>Domain Registration:</b>\n"
    if whois_result["valid"]:
        reply += (
            f"• Expires on: {whois_result['expires_at']}\n"
            f"• Days left: {whois_result['days_left']}\n"
        )
    else:
        reply += f"• ❌ WHOIS error: {whois_result['error']}\n"

    await message.answer(reply)


@dp.message(F.text.startswith("/check"))
async def check_domain_handler(message: Message):
    """
    Handler for the /check command.
    Performs a manual check of the specified domain's HTTP/HTTPS status, SSL certificate, and WHOIS info.

    Args:
        message (Message): Telegram message object.
    """
    if not is_authorized(message.from_user.id):
        await message.answer("⛔️ You do not have access to this command.")
        return

    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("⚠️ Use the command like this: <code>/check example.com</code>")
        return

    domain = parts[1].strip().lower()
    await perform_check(message, domain)


# Handler for inline check button callbacks
from aiogram.types import CallbackQuery

@dp.callback_query(F.data.startswith("check:"))
async def handle_check_callback(callback: CallbackQuery):
    """
    Callback handler for inline domain check buttons.
    Extracts the domain and performs a check.

    Args:
        callback (CallbackQuery): Telegram callback query.
    """
    domain = callback.data.split("check:")[1]
    await perform_check(callback.message, domain)
    await callback.answer()



@dp.message(F.text.startswith("/remove"))
async def remove_domain_handler(message: Message):
    """
    Handler for the /remove command.
    Removes a domain from the monitoring list for the authorized user.

    Args:
        message (Message): Telegram message object.
    """
    if not is_authorized(message.from_user.id):
        await message.answer("⛔️ You do not have access to this command.")
        return

    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("⚠️ Use the command like this: <code>/remove example.com</code>")
        return

    domain = parts[1].strip().lower()

    async with SessionLocal() as session:
        result = await session.execute(
            Domain.__table__.select().where(
                Domain.name == domain,
                Domain.user_id == message.from_user.id
            )
        )

        if not result.fetchone():
            await message.answer("ℹ️ This domain was not found in your list.")
            return

        await session.execute(
            Domain.__table__.delete().where(
                Domain.name == domain,
                Domain.user_id == message.from_user.id
            )
        )
        await session.commit()

        await message.answer(f"🗑️ Domain <b>{domain}</b> has been removed from monitoring.")



@dp.message()
async def fallback_handler(message: Message):
    """
    Fallback handler for any unrecognized input.
    Sends help instructions to the authorized user.

    Args:
        message (Message): Telegram message object.
    """
    if not is_authorized(message.from_user.id):
        return

    text = (
        "🤖 <b>Available commands:</b>\n\n"
        "<b>/add example.com</b> — add a domain for monitoring\n"
        "<b>/remove example.com</b> — remove a domain from monitoring\n"
        "<b>/list</b> — show all monitored domains\n"
        "<b>/check example.com</b> — manually check a domain\n"
        "<b>/help</b> — show this help message"
    )
    await message.answer(text)


async def main():
    """
    Main entry point of the bot.
    Sets commands, initializes the database, starts the scheduler, and begins polling.
    """
    await bot.set_my_commands([
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="list", description="List all domains"),
        BotCommand(command="help", description="Help with commands"),
    ])
    await init_db()
    scheduler.add_job(check_all_domains, "interval", minutes=5)
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
