import re
import httpx
import whois
from datetime import datetime

def is_valid_domain(domain: str) -> bool:
    """
    Простейшая валидация доменного имени.
    """
    pattern = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.[A-Za-z]{2,6}$")
    return bool(pattern.match(domain.strip().lower()))



async def check_http_https(domain: str) -> dict:
    """
    Проверяет доступность домена по HTTP и HTTPS.
    Возвращает словарь:
    {
        'http': {'status': 'ok', 'code': 200},
        'https': {'status': 'fail', 'error': 'Connection refused'}
    }
    """
    results = {}

    for protocol in ["http", "https"]:
        url = f"{protocol}://{domain}"
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                response = await client.get(url)
                results[protocol] = {
                    "status": "ok",
                    "code": response.status_code
                }
        except httpx.RequestError as e:
            results[protocol] = {
                "status": "fail",
                "error": str(e)
            }

    return results


import ssl
import socket
from datetime import datetime

def check_ssl(domain: str) -> dict:
    """
    Проверяет SSL-сертификат домена:
    - срок действия
    - дату окончания
    - издателя

    Возвращает:
    {
        "valid": True/False,
        "expires_at": "2025-06-01",
        "days_left": 47,
        "issuer": "Let's Encrypt"
    }
    """
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

        expires_str = cert['notAfter']
        expires_at = datetime.strptime(expires_str, '%b %d %H:%M:%S %Y %Z')
        days_left = (expires_at - datetime.utcnow()).days

        issuer_parts = [x[0][1] for x in cert.get("issuer", [])]
        issuer = ", ".join(issuer_parts)

        return {
            "valid": True,
            "expires_at": expires_at.strftime("%Y-%m-%d"),
            "days_left": days_left,
            "issuer": issuer
        }

    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }


def check_domain_expiry(domain: str) -> dict:
    """
    Проверяет дату окончания регистрации домена.
    Возвращает:
    {
        "valid": True,
        "expires_at": "2025-08-19",
        "days_left": 103
    }
    или
    {
        "valid": False,
        "error": "..."
    }
    """
    try:
        w = whois.whois(domain)
        expires_at = w.expiration_date

        # expiration_date может быть list или datetime
        if isinstance(expires_at, list):
            expires_at = expires_at[0]

        if not isinstance(expires_at, datetime):
            raise ValueError("Не удалось определить дату окончания.")

        days_left = (expires_at - datetime.utcnow()).days

        return {
            "valid": True,
            "expires_at": expires_at.strftime("%Y-%m-%d"),
            "days_left": days_left
        }

    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }