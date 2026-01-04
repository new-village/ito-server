"""SQLite database session management using SQLModel.

Provides database initialization and session management for user authentication.
"""

import os
from pathlib import Path
from typing import Generator

from sqlmodel import SQLModel, Session, create_engine

from app.config import get_settings

# Engine will be initialized lazily
_engine = None


def get_engine():
    """Get or create the SQLAlchemy engine.

    Returns:
        The SQLAlchemy engine instance.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        # Ensure the database directory exists
        db_path = Path(settings.DATABASE_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Build SQLite URL from path
        database_url = f"sqlite:///{db_path}"
        # SQLite-specific configuration
        connect_args = {"check_same_thread": False}
        _engine = create_engine(
            database_url,
            echo=settings.DEBUG,
            connect_args=connect_args,
        )
    return _engine


def init_db() -> None:
    """Initialize the database by creating all tables.

    This function creates all SQLModel tables defined in the application.
    Should be called during application startup.
    """
    # Import all models to ensure they're registered with SQLModel
    from app.models.user import User, RefreshToken  # noqa: F401

    engine = get_engine()
    SQLModel.metadata.create_all(engine)


def get_db_session() -> Generator[Session, None, None]:
    """Get a database session.

    Yields:
        A SQLModel Session for database operations.

    Usage:
        with get_db_session() as session:
            user = session.exec(select(User)).first()
    """
    engine = get_engine()
    with Session(engine) as session:
        yield session
