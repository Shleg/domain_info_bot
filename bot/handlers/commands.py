"""Text commands (slash and fallback)."""
from aiogram import F, Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from db.db import SessionLocal
from db.repositories import (
    create_monitoring_domain,
    ensure_user_settings,
    get_domain,
    list_domains_for_user,
    remove_monitoring_domain,
)
from bot.utils import is_valid_domain

from bot.handlers.check_execution import perform_check

commands_router = Router()


HELP_MESSAGE = (
    "🤖 <b>Available commands:</b>\n\n"
    "<b>/add example.com</b> — add a domain for monitoring\n"
    "<b>/remove example.com</b> — remove a domain from monitoring\n"
    "<b>/list</b> — show all monitored domains\n"
    "<b>/settings</b> — common settings\n"
    "<b>/check example.com</b> — manually check a domain\n"
    "<b>/help</b> — show this help message\n"
    "<b>/donate</b> — support the project via PayPal"
)


@commands_router.message(F.text == "/start")
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Hi! I'm monitoring websites. Send me a domain to start monitoring it.\n\n"
        "ℹ️ Type /help to see available commands and instructions."
    )


@commands_router.message(F.text == "/help")
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_MESSAGE)


@commands_router.message(F.text.startswith("/add"))
async def add_domain_handler(message: Message) -> None:
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


@commands_router.message(F.text == "/list")
async def list_domains_handler(message: Message) -> None:
    async with SessionLocal() as session:
        domains = await list_domains_for_user(session, message.from_user.id)

        if not domains:
            await message.answer("🔍 There are no domains in the database yet.")
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=d.name, callback_data=f"check:{d.name}")]
                for d in domains
            ]
        )

        await message.answer("📝 Select a domain to check:", reply_markup=keyboard)


@commands_router.message(F.text.startswith("/check"))
async def check_domain_handler(message: Message) -> None:
    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer(
            "⚠️ Use the command like this: <code>/check example.com</code>"
        )
        return

    domain = parts[1].strip().lower()
    await perform_check(message, domain)


@commands_router.message(F.text.startswith("/remove"))
async def remove_domain_handler(message: Message) -> None:
    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer(
            "⚠️ Use the command like this: <code>/remove example.com</code>"
        )
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

        await message.answer(
            f"🗑️ Domain <b>{domain}</b> has been removed from monitoring."
        )


@commands_router.message(F.text == "/donate")
async def cmd_donate(message: Message) -> None:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💖 Donate via PayPal",
                    url="https://www.paypal.com/donate/?hosted_button_id=7LZ3SYG7H69JY",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Get crypto address",
                    callback_data="copy_crypto",
                )
            ],
        ]
    )

    await message.answer(
        "🙏 If you'd like to support this project, you can make a donation:\n\n"
        "💳 <b>PayPal</b>: via the button below\n"
        "💸 <b>Crypto (USDT, TRC20)</b>: press the button to get the address\n\n"
        "Every contribution helps keep the bot alive and improving. Thank you! 💙",
        reply_markup=keyboard,
    )


@commands_router.message(F.text.startswith("/settings"))
async def cmd_settings(message: Message) -> None:
    parts = message.text.strip().split()
    async with SessionLocal() as session:
        if len(parts) == 2:
            domain_name = parts[1].strip().lower()
            domain_obj = await get_domain(
                session, user_id=message.from_user.id, name=domain_name
            )
            if domain_obj is None:
                await message.answer("⚠️ This domain is not in your monitoring list.")
                return

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"HTTP {'✅' if domain_obj.track_http else '❌'}",
                            callback_data=f"toggle:domain:{domain_name}:track_http",
                        ),
                        InlineKeyboardButton(
                            text=f"HTTPS {'✅' if domain_obj.track_https else '❌'}",
                            callback_data=f"toggle:domain:{domain_name}:track_https",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text=f"SSL {'✅' if domain_obj.track_ssl else '❌'}",
                            callback_data=f"toggle:domain:{domain_name}:track_ssl",
                        ),
                        InlineKeyboardButton(
                            text=f"WHOIS {'✅' if domain_obj.track_whois else '❌'}",
                            callback_data=f"toggle:domain:{domain_name}:track_whois",
                        ),
                    ],
                ]
            )

            reply = f"⚙️ <b>Settings for domain:</b> <code>{domain_name}</code>\n"
            reply += f"• HTTP: {'✅' if domain_obj.track_http else '❌'}\n"
            reply += f"• HTTPS: {'✅' if domain_obj.track_https else '❌'}\n"
            reply += f"• SSL: {'✅' if domain_obj.track_ssl else '❌'}\n"
            reply += f"• WHOIS: {'✅' if domain_obj.track_whois else '❌'}\n"
            reply += f"• SSL Warn: {domain_obj.ssl_warn_days or '—'} days\n"
            reply += f"• WHOIS Warn: {domain_obj.whois_warn_days or '—'} days\n"

            await message.answer(reply, reply_markup=keyboard)
            return

        settings = await ensure_user_settings(session, message.from_user.id)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"HTTP {'✅' if settings.track_http else '❌'}",
                        callback_data="toggle:global:track_http",
                    ),
                    InlineKeyboardButton(
                        text=f"HTTPS {'✅' if settings.track_https else '❌'}",
                        callback_data="toggle:global:track_https",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=f"SSL {'✅' if settings.track_ssl else '❌'}",
                        callback_data="toggle:global:track_ssl",
                    ),
                    InlineKeyboardButton(
                        text=f"WHOIS {'✅' if settings.track_whois else '❌'}",
                        callback_data="toggle:global:track_whois",
                    ),
                ],
            ]
        )

        reply = "⚙️ <b>Global settings:</b>\n"
        reply += f"• HTTP: {'✅' if settings.track_http else '❌'}\n"
        reply += f"• HTTPS: {'✅' if settings.track_https else '❌'}\n"
        reply += f"• SSL: {'✅' if settings.track_ssl else '❌'}\n"
        reply += f"• WHOIS: {'✅' if settings.track_whois else '❌'}\n"
        reply += f"• SSL Warn: {settings.ssl_warn_days} days\n"
        reply += f"• WHOIS Warn: {settings.whois_warn_days} days\n"

        await message.answer(reply, reply_markup=keyboard)


@commands_router.message()
async def fallback_handler(message: Message) -> None:
    await message.answer(HELP_MESSAGE)
