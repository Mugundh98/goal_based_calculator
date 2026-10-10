"""ORM models. Import every model here so Alembic can detect it."""

from app.core.database import Base

__all__ = ["Base"]
