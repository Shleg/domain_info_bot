import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine

from config import DB_URL, DEBUG

engine: AsyncEngine = create_async_engine(DB_URL, echo=DEBUG)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


def _migration_config() -> Config:
    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", DB_URL.replace("%", "%%"))
    return cfg


def _upgrade_sync() -> None:
    """Runs Alembic upgrade in a blocking context (caller may use asyncio.to_thread)."""
    command.upgrade(_migration_config(), "head")


async def init_db() -> None:
    """
    Applies Alembic migrations to ``head``.
    Новые окружения: таблицы создаёт начальная миграция.
    База уже с ``create_all`` до Alembic: один раз ``alembic stamp f8c2ab01e4a9``, затем обычные upgrade.
    """
    await asyncio.to_thread(_upgrade_sync)