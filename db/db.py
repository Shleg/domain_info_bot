from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from config import DB_URL

engine: AsyncEngine = create_async_engine(DB_URL, echo=True)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

async def init_db() -> None:
    """
    Initializes the database by creating all tables based on the defined SQLAlchemy models.
    """
    from db.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)