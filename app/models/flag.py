"""Flag models for risk flag management using SQLModel.

Defines the Flag table for SQLite storage and related schemas.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Field, SQLModel


class Flag(SQLModel, table=True):
    """Flag database model (SQLite table).

    Stores risk flag data associated with subjects.
    """

    __tablename__ = "flags"

    id: Optional[int] = Field(default=None, primary_key=True)
    flag_id: str = Field(index=True, description="Unique flag identifier")
    subject_id: str = Field(index=True, description="Subject node ID")
    rule_id: str = Field(description="Risk rule identifier")
    score: int = Field(description="Risk score")
    parameter: str = Field(default="", description="Rule parameter (country code, amount, etc.)")
    create_date: datetime = Field(description="Creation timestamp")
    create_by: str = Field(description="Creator (SYSTEM, ADMIN, etc.)")


class FlagCreate(BaseModel):
    """Schema for creating new flags.

    Allows creating multiple flags with the same flag_id but different subject_ids.
    """

    flag_id: str = PydanticField(..., description="Unique flag identifier")
    subject_ids: list[str] = PydanticField(..., min_length=1, description="List of subject node IDs")
    rule_id: str = PydanticField(..., description="Risk rule identifier")
    score: int = PydanticField(..., ge=0, description="Risk score")
    parameter: str = PydanticField(default="", description="Rule parameter")
    create_date: datetime = PydanticField(..., description="Creation timestamp")
    create_by: str = PydanticField(..., description="Creator identifier")


class FlagResponse(BaseModel):
    """Schema for flag response with grouped subject_ids.

    Returns distinct flag metadata with a list of associated subject_ids.
    """

    flag_id: str = PydanticField(..., description="Unique flag identifier")
    rule_id: str = PydanticField(..., description="Risk rule identifier")
    score: int = PydanticField(..., description="Risk score")
    parameter: str = PydanticField(..., description="Rule parameter")
    create_date: datetime = PydanticField(..., description="Creation timestamp")
    create_by: str = PydanticField(..., description="Creator identifier")
    subject_ids: list[str] = PydanticField(..., description="List of subject node IDs")


class FlagListResponse(BaseModel):
    """Schema for list of flag responses."""

    flags: list[FlagResponse] = PydanticField(default_factory=list)
    total: int = PydanticField(..., description="Total number of flags")


class FlagDeleteResponse(BaseModel):
    """Schema for flag deletion response."""

    flag_id: str = PydanticField(..., description="Deleted flag identifier")
    deleted_count: int = PydanticField(..., description="Number of records deleted")
