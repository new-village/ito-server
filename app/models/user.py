"""User models for authentication using SQLModel.

Defines the User table for SQLite storage and related schemas.
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import EmailStr
from sqlmodel import Field, SQLModel


class UserBase(SQLModel):
    """Base user model with common fields."""

    username: str = Field(unique=True, index=True, min_length=3, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)


class User(UserBase, table=True):
    """User database model (SQLite table).

    Stores user authentication data including hashed passwords.
    """

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RefreshToken(SQLModel, table=True):
    """Refresh token database model (SQLite table).

    Stores refresh tokens for session management.
    Tokens are hashed for security.
    """

    __tablename__ = "refresh_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True)  # SHA256 hash of token
    user_id: int = Field(foreign_key="users.id", index=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_revoked: bool = Field(default=False)


class UserCreate(SQLModel):
    """Schema for creating a new user."""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    email: Optional[str] = Field(default=None, max_length=255)
    is_admin: bool = Field(default=False)


class UserRead(SQLModel):
    """Schema for reading user data (excludes password)."""

    id: int
    username: str
    email: Optional[str] = None
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime


class UserUpdate(SQLModel):
    """Schema for updating user data."""

    email: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


class Token(SQLModel):
    """JWT token response schema with access and refresh tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(SQLModel):
    """Request schema for token refresh."""

    refresh_token: str


class TokenData(SQLModel):
    """Data embedded in JWT token."""

    username: Optional[str] = None
    is_admin: bool = False
