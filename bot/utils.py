import re
import httpx

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