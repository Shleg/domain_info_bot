import datetime
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, Boolean
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Domain(AsyncAttrs, Base):
    """
    Represents a domain monitored by a specific Telegram user.

    This model stores individual monitoring preferences for each domain.
    If a specific setting is None, the global setting from UserSettings is used.

    Attributes:
        id (int): Primary key.
        name (str): Domain name (e.g., "example.com").
        user_id (int): Telegram user ID who owns this domain.
        added_at (datetime): Timestamp when the domain was added.
        track_http (bool | None): Whether to check HTTP availability.
        track_https (bool | None): Whether to check HTTPS availability.
        track_ssl (bool | None): Whether to check SSL certificate validity.
        track_whois (bool | None): Whether to check domain expiration via WHOIS.
        ssl_warn_days (int | None): Days before SSL expiry to warn.
        whois_warn_days (int | None): Days before domain expiry to warn.
    """
    __tablename__ = "domains"
    __table_args__ = (
        UniqueConstraint("name", "user_id", name="uix_user_domain"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    name: str = Column(String, nullable=False, index=True)
    user_id: int = Column(Integer, nullable=False, index=True)
    added_at: datetime.datetime = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    track_http: bool = Column(Boolean, nullable=True)
    track_https: bool = Column(Boolean, nullable=True)
    track_ssl: bool = Column(Boolean, nullable=True)
    track_whois: bool = Column(Boolean, nullable=True)
    ssl_warn_days: int = Column(Integer, nullable=True)
    whois_warn_days: int = Column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"Domain(id={self.id}, name='{self.name}', user_id={self.user_id})"

class UserSettings(AsyncAttrs, Base):
    """
    Stores global monitoring preferences for a Telegram user.

    These settings act as fallbacks for each domain that doesn't override them.

    Attributes:
        user_id (int): Telegram user ID (primary key).
        track_http (bool): Whether to check HTTP availability by default.
        track_https (bool): Whether to check HTTPS availability by default.
        track_ssl (bool): Whether to check SSL certificate validity by default.
        track_whois (bool): Whether to check domain expiration via WHOIS by default.
        ssl_warn_days (int): Default days before SSL expiry to warn.
        whois_warn_days (int): Default days before domain expiry to warn.
    """
    __tablename__ = "user_settings"

    user_id: int = Column(Integer, primary_key=True)
    track_http: bool = Column(Boolean, default=True)
    track_https: bool = Column(Boolean, default=True)
    track_ssl: bool = Column(Boolean, default=True)
    track_whois: bool = Column(Boolean, default=True)
    ssl_warn_days: int = Column(Integer, default=15)
    whois_warn_days: int = Column(Integer, default=30)