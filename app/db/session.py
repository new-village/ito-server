"""SQLite database session management using SQLModel.

Provides database initialization and session management for user authentication
and flag management.
"""

import os
from pathlib import Path
from typing import Generator

from sqlmodel import SQLModel, Session, create_engine

from app.config import get_settings

# Engine will be initialized lazily
_engine = None
_flag_engine = None

# Default flag database path
FLAG_DATABASE_PATH = "data/flags.db"


def get_engine():
    """Get or create the SQLAlchemy engine for user database.

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


def get_flag_engine():
    """Get or create the SQLAlchemy engine for flag database.

    Returns:
        The SQLAlchemy engine instance for flags.
    """
    global _flag_engine
    if _flag_engine is None:
        settings = get_settings()
        # Ensure the database directory exists
        db_path = Path(FLAG_DATABASE_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Build SQLite URL from path
        database_url = f"sqlite:///{db_path}"
        # SQLite-specific configuration
        connect_args = {"check_same_thread": False}
        _flag_engine = create_engine(
            database_url,
            echo=settings.DEBUG,
            connect_args=connect_args,
        )
    return _flag_engine


def init_db() -> None:
    """Initialize the database by creating all tables.

    This function creates all SQLModel tables defined in the application.
    Should be called during application startup.
    """
    # Import all models to ensure they're registered with SQLModel
    from app.models.user import User, RefreshToken  # noqa: F401

    engine = get_engine()
    SQLModel.metadata.create_all(engine)


def init_flag_db() -> None:
    """Initialize the flag database by creating all tables.

    This function creates flag tables in the separate flag database.
    Should be called during application startup.
    """
    from app.models.flag import Flag  # noqa: F401

    engine = get_flag_engine()
    # Create only the Flag table in the flag database
    Flag.metadata.create_all(engine)


def get_db_session() -> Generator[Session, None, None]:
    """Get a database session for user database.

    Yields:
        A SQLModel Session for database operations.

    Usage:
        with get_db_session() as session:
            user = session.exec(select(User)).first()
    """
    engine = get_engine()
    with Session(engine) as session:
        yield session


def get_flag_db_session() -> Generator[Session, None, None]:
    """Get a database session for flag database.

    Yields:
        A SQLModel Session for flag database operations.

    Usage:
        with get_flag_db_session() as session:
            flag = session.exec(select(Flag)).first()
    """
    engine = get_flag_engine()
    with Session(engine) as session:
        yield session
