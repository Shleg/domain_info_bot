"""
Domain monitoring: effective settings resolution, probes, alerting rules,
and Telegram message formatting for check results.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from db.models import Domain, UserSettings
from bot.utils import check_http_https, check_ssl, check_domain_expiry


@dataclass(frozen=True)
class EffectiveMonitoringSettings:
    track_http: bool
    track_https: bool
    track_ssl: bool
    track_whois: bool
    ssl_warn_days: int
    whois_warn_days: int


@dataclass
class CheckReport:
    """Raw probe results returned by ``run_full_check``."""

    http_https: dict[str, dict[str, Any]] | None
    ssl: dict[str, Any] | None
    whois: dict[str, Any] | None


def resolve_effective_settings(
    domain_row: Domain | Any | None,
    user_settings: UserSettings | None,
) -> EffectiveMonitoringSettings:
    """
    Merge per-domain overrides with global user defaults.
    ``domain_row`` may be ``None`` (ad-hoc check) or any object with Domain-like columns
    (e.g. a SQLAlchemy ``Row`` from ``domains``).
    """
    us = user_settings
    if domain_row is None:
        return EffectiveMonitoringSettings(
            track_http=bool(us.track_http) if us else True,
            track_https=bool(us.track_https) if us else True,
            track_ssl=bool(us.track_ssl) if us else True,
            track_whois=bool(us.track_whois) if us else True,
            ssl_warn_days=int(us.ssl_warn_days) if us else 15,
            whois_warn_days=int(us.whois_warn_days) if us else 30,
        )

    track_http = (
        domain_row.track_http
        if domain_row.track_http is not None
        else bool(us.track_http if us else True)
    )
    track_https = (
        domain_row.track_https
        if domain_row.track_https is not None
        else bool(us.track_https if us else True)
    )
    track_ssl = (
        domain_row.track_ssl
        if domain_row.track_ssl is not None
        else bool(us.track_ssl if us else True)
    )
    track_whois = (
        domain_row.track_whois
        if domain_row.track_whois is not None
        else bool(us.track_whois if us else True)
    )
    ssl_warn_days = domain_row.ssl_warn_days or (
        int(us.ssl_warn_days) if us else 15
    )
    whois_warn_days = domain_row.whois_warn_days or (
        int(us.whois_warn_days) if us else 30
    )

    return EffectiveMonitoringSettings(
        track_http=track_http,
        track_https=track_https,
        track_ssl=track_ssl,
        track_whois=track_whois,
        ssl_warn_days=ssl_warn_days,
        whois_warn_days=whois_warn_days,
    )


async def run_full_check(
    domain: str, settings: EffectiveMonitoringSettings
) -> CheckReport:
    """Run HTTP/HTTPS, SSL, and WHOIS checks according to ``settings``."""
    http_https = (
        await check_http_https(domain)
        if settings.track_http or settings.track_https
        else None
    )
    ssl_result = await check_ssl(domain) if settings.track_ssl else None
    whois_result = (
        await check_domain_expiry(domain) if settings.track_whois else None
    )
    return CheckReport(http_https=http_https, ssl=ssl_result, whois=whois_result)


def should_alert_availability(
    http_https: dict[str, dict[str, Any]] | None,
    settings: EffectiveMonitoringSettings,
) -> list[str]:
    """Return bullet lines for Telegram when HTTP/HTTPS should notify."""
    if http_https is None:
        return []
    problems: list[str] = []
    if settings.track_http and http_https.get("http", {}).get("status") != "ok":
        problems.append(
            f"HTTP ❌ ({http_https['http'].get('error', 'error')})"
        )
    if settings.track_https and http_https.get("https", {}).get("status") != "ok":
        problems.append(
            f"HTTPS ❌ ({http_https['https'].get('error', 'error')})"
        )
    return problems


def should_alert_expiry(
    ssl_result: dict[str, Any] | None,
    whois_result: dict[str, Any] | None,
    settings: EffectiveMonitoringSettings,
) -> list[str]:
    """Return bullet lines for Telegram when SSL / domain expiry should notify."""
    out: list[str] = []
    if settings.track_ssl and ssl_result is not None:
        if not ssl_result["valid"] or ssl_result.get("days_left", 0) < settings.ssl_warn_days:
            out.append("SSL certificate is expiring or invalid ⚠️")
    if settings.track_whois and whois_result is not None:
        if not whois_result["valid"] or whois_result.get("days_left", 0) < settings.whois_warn_days:
            out.append("Domain registration is expiring ⚠️")
    return out


def format_check_report_message(domain: str, report: CheckReport, settings: EffectiveMonitoringSettings) -> str:
    """Format a manual /check reply (HTML snippets for Aiogram ParseMode.HTML)."""
    reply = f"📊 Check results for <b>{domain}</b>:\n"

    if settings.track_http or settings.track_https:
        results = report.http_https or {}
        for proto in ("http", "https"):
            if (proto == "http" and settings.track_http) or (
                proto == "https" and settings.track_https
            ):
                res = results.get(proto) or {}
                if res.get("status") == "ok":
                    reply += f"• <b>{proto.upper()}</b>: ✅ {res['code']}\n"
                else:
                    reply += f"• <b>{proto.upper()}</b>: ❌ {res.get('error', 'error')}\n"

    if settings.track_ssl:
        reply += "\n🔐 <b>SSL Certificate:</b>\n"
        ssl_result = report.ssl or {"valid": False, "error": "not run"}
        if ssl_result.get("valid"):
            reply += (
                f"• Issuer: {ssl_result['issuer']}\n"
                f"• Valid until: {ssl_result['expires_at']}\n"
                f"• Days left: {ssl_result['days_left']}\n"
            )
        else:
            reply += f"• ❌ SSL check error: {ssl_result.get('error', 'unknown')}\n"

    if settings.track_whois:
        reply += "\n🌐 <b>Domain Registration:</b>\n"
        whois_result = report.whois or {"valid": False, "error": "not run"}
        if whois_result.get("valid"):
            reply += (
                f"• Expires on: {whois_result['expires_at']}\n"
                f"• Days left: {whois_result['days_left']}\n"
            )
        else:
            reply += f"• ❌ WHOIS error: {whois_result.get('error', 'unknown')}\n"

    return reply
