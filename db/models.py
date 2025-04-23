import datetime
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Domain(AsyncAttrs, Base):
    """
    Represents a domain added by a specific Telegram user for monitoring.

    Attributes:
        id (int): Primary key of the domain record.
        name (str): The domain name (e.g., "example.com").
        user_id (int): Telegram user ID who added this domain.
        added_at (datetime): Timestamp when the domain was added.
    """
    __tablename__ = "domains"
    __table_args__ = (
        UniqueConstraint("name", "user_id", name="uix_user_domain"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    name: str = Column(String, nullable=False, index=True)
    user_id: int = Column(Integer, nullable=False, index=True)
    added_at: datetime.datetime = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"Domain(id={self.id}, name='{self.name}', user_id={self.user_id})"