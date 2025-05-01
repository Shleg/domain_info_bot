from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton

from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import asyncio

from sqlalchemy import select

from config import BOT_TOKEN
from db.db import init_db
from db.models import Domain
from db.models import UserSettings
from db.db import SessionLocal
from bot.utils import is_valid_domain, check_http_https, check_ssl, check_domain_expiry
from bot.scheduler import scheduler, check_all_domains

from config import ALLOWED_USER_IDS

from bot.handlers.settings import settings_router

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

    await message.answer(
        "👋 Hi! I'm monitoring websites. Send me a domain to start monitoring it.\n\n"
        "ℹ️ Type /help to see available commands and instructions.")


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
        "🤖 <b>Available commands:</b>\n\n"
        "<b>/add example.com</b> — add a domain for monitoring\n"
        "<b>/remove example.com</b> — remove a domain from monitoring\n"
        "<b>/list</b> — show all monitored domains\n"
        "<b>/settings</b> — common settings\n"
        # "<b>/settings example.com</b> — individual settings\n"
        "<b>/check example.com</b> — manually check a domain\n"
        "<b>/help</b> — show this help message\n"
        "<b>/donate </b> — support the project via PayPal"
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



from typing import Union
from aiogram.types import Message, CallbackQuery

async def perform_check(source: Union[Message, CallbackQuery], domain: str) -> None:
    if isinstance(source, CallbackQuery):
        user_id = source.from_user.id
        message = source.message
    else:
        user_id = source.from_user.id
        message = source

    await message.answer(f"🔍 Checking <b>{domain}</b>...")

    async with SessionLocal() as session:
        result = await session.execute(
            select(Domain).where(
                Domain.name == domain,
                Domain.user_id == user_id
            )
        )
        domain_row = result.scalar_one_or_none()
        if domain_row is None:
            await message.answer("⚠️ Domain not found.")
            return

        settings = await session.get(UserSettings, user_id)
        if settings is None:
            settings = UserSettings(user_id=user_id)
            session.add(settings)
            await session.commit()

        # Determine which settings to use
        track_http = domain_row.track_http if domain_row.track_http is not None else settings.track_http
        track_https = domain_row.track_https if domain_row.track_https is not None else settings.track_https
        track_ssl = domain_row.track_ssl if domain_row.track_ssl is not None else settings.track_ssl
        track_whois = domain_row.track_whois if domain_row.track_whois is not None else settings.track_whois
        ssl_warn_days = domain_row.ssl_warn_days or settings.ssl_warn_days
        whois_warn_days = domain_row.whois_warn_days or settings.whois_warn_days

    reply = f"📊 Check results for <b>{domain}</b>:\n"

    if track_http or track_https:
        results = await check_http_https(domain)
        for proto in ["http", "https"]:
            if (proto == "http" and track_http) or (proto == "https" and track_https):
                res = results.get(proto)
                if res["status"] == "ok":
                    reply += f"• <b>{proto.upper()}</b>: ✅ {res['code']}\n"
                else:
                    reply += f"• <b>{proto.upper()}</b>: ❌ {res['error']}\n"

    if track_ssl:
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

    if track_whois:
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
    await perform_check(callback, domain)
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


@dp.message(F.text == "/donate")
async def cmd_donate(message: Message):
    """
    Handler for the /donate command.
    Sends a message with a PayPal donation link.
    """
    if not is_authorized(message.from_user.id):
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💖 Donate via PayPal", url="https://www.paypal.com/donate/?hosted_button_id=7LZ3SYG7H69JY")],
        [InlineKeyboardButton(text="📋 Get crypto address", callback_data="copy_crypto")]
    ])

    await message.answer(
        "🙏 If you'd like to support this project, you can make a donation:\n\n"
        "💳 <b>PayPal</b>: via the button below\n"
        "💸 <b>Crypto (USDT, TRC20)</b>: press the button to get the address\n\n"
        "Every contribution helps keep the bot alive and improving. Thank you! 💙",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "copy_crypto")
async def copy_crypto_handler(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("⛔️ Not allowed", show_alert=True)
        return

    await callback.message.answer("Here is the wallet address 👇")
    await callback.message.answer("<code>TUGi5pzSnM6kqpXMHkXiPL6yFyGmC9vAje</code>")


@dp.message(F.text.startswith("/settings"))
async def cmd_settings(message: Message):
    """
    Handler for the /settings command.
    Displays user-specific or domain-specific monitoring settings with toggle buttons.

    Args:
        message (Message): Telegram message object.
    """
    if not is_authorized(message.from_user.id):
        await message.answer("⛔️ You do not have access to this command.")
        return

    parts = message.text.strip().split()
    async with SessionLocal() as session:
        # Domain-specific settings
        if len(parts) == 2:
            domain_name = parts[1].strip().lower()
            domain_result = await session.execute(
                Domain.__table__.select().where(
                    Domain.name == domain_name,
                    Domain.user_id == message.from_user.id
                )
            )
            domain = domain_result.fetchone()
            if not domain:
                await message.answer("⚠️ This domain is not in your monitoring list.")
                return

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"HTTP {'✅' if domain.track_http else '❌'}",
                        callback_data=f"toggle:domain:{domain_name}:track_http"
                    ),
                    InlineKeyboardButton(
                        text=f"HTTPS {'✅' if domain.track_https else '❌'}",
                        callback_data=f"toggle:domain:{domain_name}:track_https"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"SSL {'✅' if domain.track_ssl else '❌'}",
                        callback_data=f"toggle:domain:{domain_name}:track_ssl"
                    ),
                    InlineKeyboardButton(
                        text=f"WHOIS {'✅' if domain.track_whois else '❌'}",
                        callback_data=f"toggle:domain:{domain_name}:track_whois"
                    )
                ]
            ])

            reply = f"⚙️ <b>Settings for domain:</b> <code>{domain_name}</code>\n"
            reply += f"• HTTP: {'✅' if domain.track_http else '❌'}\n"
            reply += f"• HTTPS: {'✅' if domain.track_https else '❌'}\n"
            reply += f"• SSL: {'✅' if domain.track_ssl else '❌'}\n"
            reply += f"• WHOIS: {'✅' if domain.track_whois else '❌'}\n"
            reply += f"• SSL Warn: {domain.ssl_warn_days or '—'} days\n"
            reply += f"• WHOIS Warn: {domain.whois_warn_days or '—'} days\n"

            await message.answer(reply, reply_markup=keyboard)
            return

        # Global settings
        settings = await session.get(UserSettings, message.from_user.id)
        if not settings:
            settings = UserSettings(user_id=message.from_user.id)
            session.add(settings)
            await session.commit()

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"HTTP {'✅' if settings.track_http else '❌'}",
                    callback_data="toggle:global:track_http"
                ),
                InlineKeyboardButton(
                    text=f"HTTPS {'✅' if settings.track_https else '❌'}",
                    callback_data="toggle:global:track_https"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"SSL {'✅' if settings.track_ssl else '❌'}",
                    callback_data="toggle:global:track_ssl"
                ),
                InlineKeyboardButton(
                    text=f"WHOIS {'✅' if settings.track_whois else '❌'}",
                    callback_data="toggle:global:track_whois"
                )
            ]
        ])

        reply = f"⚙️ <b>Global settings:</b>\n"
        reply += f"• HTTP: {'✅' if settings.track_http else '❌'}\n"
        reply += f"• HTTPS: {'✅' if settings.track_https else '❌'}\n"
        reply += f"• SSL: {'✅' if settings.track_ssl else '❌'}\n"
        reply += f"• WHOIS: {'✅' if settings.track_whois else '❌'}\n"
        reply += f"• SSL Warn: {settings.ssl_warn_days} days\n"
        reply += f"• WHOIS Warn: {settings.whois_warn_days} days\n"

        await message.answer(reply, reply_markup=keyboard)


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
        "<b>/settings</b> — common settings\n"
        # "<b>/settings example.com</b> — individual settings\n"
        "<b>/check example.com</b> — manually check a domain\n"
        "<b>/help</b> — show this help message\n"
        "<b>/donate </b> — support the project via PayPal"
    )
    await message.answer(text)

async def main():
    """
    Main entry point of the bot.
    Sets commands, initializes the database, starts the scheduler, and begins polling.
    """
    await bot.delete_my_commands()
    await bot.set_my_commands([
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="list", description="List all domains"),
        BotCommand(command="settings", description="Show or edit monitoring settings"),
        BotCommand(command="donate", description="Support the project via PayPal"),
        BotCommand(command="help", description="Help with commands"),
    ])
    await init_db()
    scheduler.add_job(check_all_domains, "interval", minutes=5)
    scheduler.start()
    dp.include_router(settings_router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
