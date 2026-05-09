"""
Small async repositories: ``select(...)`` against ORM models only (no Core table API).
"""
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Domain, UserSettings


async def get_domain(
    session: AsyncSession, *, user_id: int, name: str
) -> Domain | None:
    r = await session.execute(
        select(Domain).where(Domain.user_id == user_id, Domain.name == name)
    )
    return r.scalar_one_or_none()


async def list_domains_for_user(session: AsyncSession, user_id: int) -> list[Domain]:
    r = await session.scalars(
        select(Domain).where(Domain.user_id == user_id).order_by(Domain.name)
    )
    return list(r.all())


async def list_all_domains(session: AsyncSession) -> list[Domain]:
    r = await session.scalars(select(Domain).order_by(Domain.id))
    return list(r.all())


async def domain_exists(
    session: AsyncSession, *, user_id: int, name: str
) -> bool:
    return (await get_domain(session, user_id=user_id, name=name)) is not None


async def create_monitoring_domain(
    session: AsyncSession, *, user_id: int, name: str
) -> bool:
    """Return ``False`` if the domain already exists for this user."""
    if await domain_exists(session, user_id=user_id, name=name):
        return False
    session.add(Domain(name=name, user_id=user_id))
    await session.commit()
    return True


async def remove_monitoring_domain(
    session: AsyncSession, *, user_id: int, name: str
) -> bool:
    """Return ``True`` if a row was deleted."""
    deleted = await session.execute(
        delete(Domain).where(Domain.user_id == user_id, Domain.name == name)
    )
    await session.commit()
    return deleted.rowcount > 0


async def ensure_user_settings(session: AsyncSession, user_id: int) -> UserSettings:
    row = await session.get(UserSettings, user_id)
    if row is not None:
        return row
    row = UserSettings(user_id=user_id)
    session.add(row)
    await session.commit()
    return row
