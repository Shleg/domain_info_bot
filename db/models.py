import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Domain(AsyncAttrs, Base):
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    user_id = Column(Integer, nullable=False)
    added_at = Column(DateTime, default=datetime.datetime.utcnow)
