"""Flag API router for risk flag management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db.session import get_flag_db_session
from app.models.flag import (
    Flag,
    FlagCreate,
    FlagResponse,
    FlagListResponse,
    FlagDeleteResponse,
)
from app.models.user import User
from app.auth.dependencies import get_current_active_user

router = APIRouter(prefix="/flag", tags=["flag"])


def _get_flag_db():
    """Dependency to get flag database session."""
    yield from get_flag_db_session()


def _group_flags_by_flag_id(flags: list[Flag]) -> list[FlagResponse]:
    """Group flag records by flag_id and return FlagResponse list.

    Args:
        flags: List of Flag records.

    Returns:
        List of FlagResponse with grouped subject_ids.
    """
    flag_groups: dict[str, FlagResponse] = {}

    for flag in flags:
        if flag.flag_id not in flag_groups:
            flag_groups[flag.flag_id] = FlagResponse(
                flag_id=flag.flag_id,
                rule_id=flag.rule_id,
                score=flag.score,
                parameter=flag.parameter,
                create_date=flag.create_date,
                create_by=flag.create_by,
                subject_ids=[flag.subject_id],
            )
        else:
            flag_groups[flag.flag_id].subject_ids.append(flag.subject_id)

    return list(flag_groups.values())


@router.get(
    "/{subject_id}",
    response_model=FlagListResponse,
    summary="Get flags by subject ID",
    description="Get all flags associated with the given subject_id and all related flags sharing the same flag_id.",
)
async def get_flags_by_subject(
    subject_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(_get_flag_db),
) -> FlagListResponse:
    """Get flags by subject_id.

    First finds all flag_ids associated with the given subject_id,
    then retrieves all flags with those flag_ids.

    Args:
        subject_id: The subject node ID to search for.
        current_user: The authenticated user (injected by dependency).
        session: Database session.

    Returns:
        FlagListResponse with grouped flags.
    """
    # Step 1: Find all flag_ids for the given subject_id
    statement = select(Flag.flag_id).where(Flag.subject_id == subject_id).distinct()
    flag_ids = session.exec(statement).all()

    if not flag_ids:
        return FlagListResponse(flags=[], total=0)

    # Step 2: Get all flags with those flag_ids
    statement = select(Flag).where(Flag.flag_id.in_(flag_ids))
    all_flags = session.exec(statement).all()

    # Step 3: Group by flag_id
    grouped_flags = _group_flags_by_flag_id(list(all_flags))

    return FlagListResponse(flags=grouped_flags, total=len(grouped_flags))


@router.post(
    "",
    response_model=FlagResponse,
    status_code=201,
    summary="Create new flags",
    description="Create new flag records for multiple subject_ids with the same flag_id.",
)
async def create_flag(
    flag_data: FlagCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(_get_flag_db),
) -> FlagResponse:
    """Create new flag records.

    Creates a flag record for each subject_id in the request,
    all sharing the same flag_id.

    Args:
        flag_data: The flag creation data.
        current_user: The authenticated user (injected by dependency).
        session: Database session.

    Returns:
        FlagResponse with created flag data.

    Raises:
        HTTPException: If flag_id already exists.
    """
    # Check if flag_id already exists
    existing = session.exec(
        select(Flag).where(Flag.flag_id == flag_data.flag_id)
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Flag with flag_id '{flag_data.flag_id}' already exists"
        )

    # Create flag records for each subject_id
    created_flags = []
    for subject_id in flag_data.subject_ids:
        flag = Flag(
            flag_id=flag_data.flag_id,
            subject_id=subject_id,
            rule_id=flag_data.rule_id,
            score=flag_data.score,
            parameter=flag_data.parameter,
            create_date=flag_data.create_date,
            create_by=flag_data.create_by,
        )
        session.add(flag)
        created_flags.append(flag)

    session.commit()

    # Refresh all flags to get their IDs
    for flag in created_flags:
        session.refresh(flag)

    return FlagResponse(
        flag_id=flag_data.flag_id,
        rule_id=flag_data.rule_id,
        score=flag_data.score,
        parameter=flag_data.parameter,
        create_date=flag_data.create_date,
        create_by=flag_data.create_by,
        subject_ids=flag_data.subject_ids,
    )


@router.delete(
    "/{flag_id}",
    response_model=FlagDeleteResponse,
    summary="Delete flags by flag ID",
    description="Delete all flag records associated with the given flag_id.",
)
async def delete_flag(
    flag_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(_get_flag_db),
) -> FlagDeleteResponse:
    """Delete all flag records by flag_id.

    Args:
        flag_id: The flag identifier to delete.
        current_user: The authenticated user (injected by dependency).
        session: Database session.

    Returns:
        FlagDeleteResponse with deletion count.

    Raises:
        HTTPException: If flag_id not found.
    """
    # Find all flags with the given flag_id
    statement = select(Flag).where(Flag.flag_id == flag_id)
    flags = session.exec(statement).all()

    if not flags:
        raise HTTPException(
            status_code=404,
            detail=f"Flag with flag_id '{flag_id}' not found"
        )

    deleted_count = len(flags)

    # Delete all matching flags
    for flag in flags:
        session.delete(flag)

    session.commit()

    return FlagDeleteResponse(flag_id=flag_id, deleted_count=deleted_count)
