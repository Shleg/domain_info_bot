from aiogram import Bot, Dispatcher, F
from typing import Union

from aiogram.types import Message, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import asyncio

from config import BOT_TOKEN, CHECK_INTERVAL_MIN, SSL_CRON_HOUR, SSL_CRON_MINUTE
from db.db import init_db
from db.db import SessionLocal
from db.repositories import (
    create_monitoring_domain,
    ensure_user_settings,
    get_domain,
    list_domains_for_user,
    remove_monitoring_domain,
)
from bot.utils import is_valid_domain
from bot.scheduler import (
    scheduler,
    check_http_https_domains,
    check_ssl_whois_domains,
    set_bot,
)
from services.monitoring import (
    resolve_effective_settings,
    run_full_check,
    format_check_report_message,
)

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
        if not await create_monitoring_domain(
            session,
            user_id=message.from_user.id,
            name=domain,
        ):
            await message.answer("ℹ️ This domain is already being monitored.")
            return

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

        domains = await list_domains_for_user(session, message.from_user.id)

        if not domains:
            await message.answer("🔍 There are no domains in the database yet.")
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=d.name, callback_data=f"check:{d.name}")]
            for d in domains
        ])

        await message.answer("📝 Select a domain to check:", reply_markup=keyboard)



async def perform_check(source: Union[Message, CallbackQuery], domain: str) -> None:
    if isinstance(source, CallbackQuery):
        user_id = source.from_user.id
        message = source.message
    else:
        user_id = source.from_user.id
        message = source

    await message.answer(f"🔍 Checking <b>{domain}</b>...")

    async with SessionLocal() as session:
        domain_row = await get_domain(session, user_id=user_id, name=domain)
        settings = await ensure_user_settings(session, user_id)

    effective = resolve_effective_settings(domain_row, settings)
    report = await run_full_check(domain, effective)
    reply = format_check_report_message(domain, report, effective)
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
        if not await remove_monitoring_domain(
            session,
            user_id=message.from_user.id,
            name=domain,
        ):
            await message.answer("ℹ️ This domain was not found in your list.")
            return

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
            domain_obj = await get_domain(
                session, user_id=message.from_user.id, name=domain_name
            )
            if domain_obj is None:
                await message.answer("⚠️ This domain is not in your monitoring list.")
                return

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"HTTP {'✅' if domain_obj.track_http else '❌'}",
                        callback_data=f"toggle:domain:{domain_name}:track_http"
                    ),
                    InlineKeyboardButton(
                        text=f"HTTPS {'✅' if domain_obj.track_https else '❌'}",
                        callback_data=f"toggle:domain:{domain_name}:track_https"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"SSL {'✅' if domain_obj.track_ssl else '❌'}",
                        callback_data=f"toggle:domain:{domain_name}:track_ssl"
                    ),
                    InlineKeyboardButton(
                        text=f"WHOIS {'✅' if domain_obj.track_whois else '❌'}",
                        callback_data=f"toggle:domain:{domain_name}:track_whois"
                    )
                ]
            ])

            reply = f"⚙️ <b>Settings for domain:</b> <code>{domain_name}</code>\n"
            reply += f"• HTTP: {'✅' if domain_obj.track_http else '❌'}\n"
            reply += f"• HTTPS: {'✅' if domain_obj.track_https else '❌'}\n"
            reply += f"• SSL: {'✅' if domain_obj.track_ssl else '❌'}\n"
            reply += f"• WHOIS: {'✅' if domain_obj.track_whois else '❌'}\n"
            reply += f"• SSL Warn: {domain_obj.ssl_warn_days or '—'} days\n"
            reply += f"• WHOIS Warn: {domain_obj.whois_warn_days or '—'} days\n"

            await message.answer(reply, reply_markup=keyboard)
            return

        # Global settings
        settings = await ensure_user_settings(session, message.from_user.id)

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
    set_bot(bot)
    # scheduler.add_job(check_all_domains, "interval", minutes=10)
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
    dp.include_router(settings_router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
