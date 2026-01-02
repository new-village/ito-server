"""User models for authentication using SQLModel.

Defines the User table for SQLite storage and related schemas.
"""

from datetime import datetime
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


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
    """JWT token response schema."""

    access_token: str
    token_type: str = "bearer"


class TokenData(SQLModel):
    """Data embedded in JWT token."""

    username: Optional[str] = None
    is_admin: bool = False
