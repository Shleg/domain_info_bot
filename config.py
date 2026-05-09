import os
from dotenv import load_dotenv

load_dotenv()


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


DEBUG = _env_truthy("DEBUG")


def _parse_allowed_user_ids(raw: str | None) -> list[int]:
    if not raw or not raw.strip():
        return []
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        ids.append(int(part))
    return ids


BOT_TOKEN = os.getenv("BOT_TOKEN")

ALLOWED_USER_IDS = _parse_allowed_user_ids(os.getenv("ALLOWED_USER_IDS"))

DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_NAME = os.getenv("POSTGRES_DB")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = int(os.getenv("POSTGRES_PORT", 5432))

DB_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Scheduler: HTTP/HTTPS interval (minutes)
CHECK_INTERVAL_MIN = max(1, int(os.getenv("CHECK_INTERVAL_MIN", "10")))


def _parse_ssl_cron(raw: str | None) -> tuple[int, int]:
    """
    Daily SSL/WHOIS job time: ``H:MM`` or ``H MM`` (24h, server timezone, usually UTC in Docker).
    Examples: ``4:00``, ``04:30``, ``4 0``.
    """
    s = (raw or "4:00").strip()
    if not s:
        return 4, 0
    if ":" in s:
        h, m = s.split(":", 1)
        return int(h.strip()) % 24, int(m.strip()) % 60
    parts = s.split()
    if len(parts) >= 2:
        return int(parts[0]) % 24, int(parts[1]) % 60
    if len(parts) == 1:
        return int(parts[0]) % 24, 0
    return 4, 0


SSL_CRON_HOUR, SSL_CRON_MINUTE = _parse_ssl_cron(os.getenv("SSL_CRON"))