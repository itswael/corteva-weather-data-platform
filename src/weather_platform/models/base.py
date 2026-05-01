"""Base ORM model and declarative registry.

This module provides the SQLAlchemy declarative base and abstract base
entity model with common fields (id, created_at) inherited by all ORM models.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative registry for all ORM models.
    
    All model classes should inherit from Base to be automatically
    registered with the metadata registry for migration tracking.
    """
    pass


class BaseEntity(Base):
    """Abstract base model providing common fields for all entities.
    
    Attributes:
        id: Primary key (auto-incrementing 64-bit integer)
        created_at: Timestamp when entity was created (server-side default to now())
    
    This class should be inherited by all concrete ORM models to provide
    consistent primary key and audit timestamp columns.
    """
    __abstract__ = True

    # Auto-incrementing primary key (64-bit allows very large IDs)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Creation timestamp with server-side default (handles timezone-aware databases)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
