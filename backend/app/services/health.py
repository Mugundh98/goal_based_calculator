"""Checks that the database is reachable and the pgvector extension is installed."""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import SessionLocal
from app.schemas.health import DatabaseStatus


def check_database() -> DatabaseStatus:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            has_vector = db.execute(
                text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            ).scalar_one()
        return DatabaseStatus(connected=True, pgvector=bool(has_vector))
    except SQLAlchemyError as exc:
        return DatabaseStatus(connected=False, pgvector=False, error=type(exc).__name__)
