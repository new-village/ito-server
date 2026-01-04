"""Authentication API endpoints.

Provides:
- /login: OAuth2 password flow login (returns JWT access token + refresh token)
- /refresh: Get new access token using refresh token
- /logout: Invalidate refresh token (end session)
- /me: Get current user info
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.auth.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)
from app.auth.dependencies import get_current_active_user
from app.config import get_settings
from app.db.session import get_db_session
from app.models.user import (
    User,
    UserRead,
    Token,
    RefreshToken,
    RefreshTokenRequest,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def _create_tokens(user: User, session: Session) -> Token:
    """Create access and refresh tokens for a user.

    Args:
        user: The authenticated user.
        session: Database session.

    Returns:
        Token containing access_token and refresh_token.
    """
    settings = get_settings()

    # Create short-lived access token
    access_token = create_access_token(
        data={"sub": user.username, "is_admin": user.is_admin}
    )

    # Create long-lived refresh token
    refresh_token = generate_refresh_token()
    refresh_token_hash = hash_refresh_token(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    # Store refresh token in database
    db_refresh_token = RefreshToken(
        token_hash=refresh_token_hash,
        user_id=user.id,
        expires_at=expires_at,
    )
    session.add(db_refresh_token)
    session.commit()

    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/login",
    response_model=Token,
    summary="Login and get access token",
    description="OAuth2 password flow login. Returns a short-lived JWT access token and a long-lived refresh token.",
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_db_session)],
) -> Token:
    """Authenticate user and return JWT access token + refresh token.

    Args:
        form_data: OAuth2 password request form (username, password).
        session: Database session.

    Returns:
        Token containing access_token and refresh_token.

    Raises:
        HTTPException: If authentication fails.
    """
    # Find user by username
    statement = select(User).where(User.username == form_data.username)
    user = session.exec(statement).first()

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return _create_tokens(user, session)


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token",
    description="Get a new access token using a valid refresh token. Also rotates the refresh token for security.",
)
async def refresh_token(
    request: RefreshTokenRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> Token:
    """Get new access token using refresh token.

    This also rotates the refresh token (issues a new one and invalidates the old).

    Args:
        request: Request containing the refresh token.
        session: Database session.

    Returns:
        Token containing new access_token and new refresh_token.

    Raises:
        HTTPException: If refresh token is invalid or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Hash the provided token and look it up
    token_hash = hash_refresh_token(request.refresh_token)
    statement = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    db_token = session.exec(statement).first()

    if db_token is None:
        raise credentials_exception

    # Check if token is revoked
    if db_token.is_revoked:
        raise credentials_exception

    # Check if token is expired
    now = datetime.now(timezone.utc)
    # Handle both naive and aware datetimes from database
    expires_at = db_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < now:
        # Clean up expired token
        session.delete(db_token)
        session.commit()
        raise credentials_exception

    # Get the user
    statement = select(User).where(User.id == db_token.user_id)
    user = session.exec(statement).first()

    if user is None or not user.is_active:
        raise credentials_exception

    # Revoke the old refresh token (token rotation for security)
    db_token.is_revoked = True
    session.add(db_token)
    session.commit()

    # Create new tokens
    return _create_tokens(user, session)


@router.post(
    "/logout",
    summary="Logout and invalidate refresh token",
    description="Invalidate the refresh token to end the session. The access token will expire naturally.",
)
async def logout(
    request: RefreshTokenRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    """Logout by invalidating the refresh token.

    Note: The access token will remain valid until it expires (short-lived).
    For immediate invalidation of all sessions, use /logout-all.

    Args:
        request: Request containing the refresh token to invalidate.
        session: Database session.

    Returns:
        Success message.
    """
    # Hash the provided token and look it up
    token_hash = hash_refresh_token(request.refresh_token)
    statement = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    db_token = session.exec(statement).first()

    if db_token is not None:
        # Revoke the token
        db_token.is_revoked = True
        session.add(db_token)
        session.commit()

    # Always return success (don't reveal if token existed)
    return {"message": "Successfully logged out"}


@router.post(
    "/logout-all",
    summary="Logout from all sessions",
    description="Invalidate all refresh tokens for the current user. Requires authentication.",
)
async def logout_all(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    """Logout from all sessions by invalidating all refresh tokens.

    Args:
        current_user: The authenticated user.
        session: Database session.

    Returns:
        Success message with count of invalidated sessions.
    """
    # Find all active refresh tokens for the user
    statement = select(RefreshToken).where(
        RefreshToken.user_id == current_user.id,
        RefreshToken.is_revoked == False,
    )
    tokens = session.exec(statement).all()

    # Revoke all tokens
    count = 0
    for token in tokens:
        token.is_revoked = True
        session.add(token)
        count += 1

    session.commit()

    return {"message": f"Successfully logged out from {count} session(s)"}


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user",
    description="Get the currently authenticated user's information.",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserRead:
    """Get the current authenticated user's information.

    Args:
        current_user: The authenticated user from JWT token.

    Returns:
        UserRead containing user information (excluding password).
    """
    return UserRead(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )
