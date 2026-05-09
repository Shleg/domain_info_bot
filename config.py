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