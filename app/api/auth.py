"""Authentication API endpoints.

Provides:
- /login: OAuth2 password flow login (returns JWT token)
- /me: Get current user info
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.auth.security import create_access_token, verify_password
from app.auth.dependencies import get_current_active_user
from app.db.session import get_db_session
from app.models.user import User, UserRead, Token

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/login",
    response_model=Token,
    summary="Login and get access token",
    description="OAuth2 password flow login. Returns a JWT access token.",
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_db_session)],
) -> Token:
    """Authenticate user and return JWT access token.

    Args:
        form_data: OAuth2 password request form (username, password).
        session: Database session.

    Returns:
        Token containing the JWT access token.

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

    # Create access token
    access_token = create_access_token(
        data={"sub": user.username, "is_admin": user.is_admin}
    )

    return Token(access_token=access_token)


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
