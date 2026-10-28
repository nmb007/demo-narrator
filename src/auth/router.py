"""Auth API routes."""

from typing import Annotated

from asyncer import asyncify
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from src.auth import service as auth_service
from src.auth.exceptions import EmailAlreadyRegistered, InvalidCredentials
from src.auth.schemas import SignupRequest, TokenResponse, UserResponse
from src.schemas import error_response, success_response

router = APIRouter(prefix="/auth", tags=["auth"])

_USER_EXAMPLE = {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "you@example.com",
    "created_at": "2026-01-15T12:00:00Z",
}
_TOKEN_EXAMPLE = {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
}


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    summary="Sign up",
    description="Create a new user account.",
    responses={
        status.HTTP_201_CREATED: success_response(
            model=UserResponse,
            description="User created",
            example=_USER_EXAMPLE,
        ),
        status.HTTP_409_CONFLICT: error_response(
            description="Email already registered",
            detail="Email already registered",
        ),
    },
)
async def signup(payload: SignupRequest) -> UserResponse:
    try:
        user = await asyncify(auth_service.signup)(payload.email, payload.password)
    except EmailAlreadyRegistered as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc
    return UserResponse(id=user.id, email=user.email, created_at=user.created_at)


@router.post(
    "/login",
    summary="Log in",
    description="Exchange email and password for a JWT access token.",
    responses={
        status.HTTP_200_OK: success_response(
            model=TokenResponse,
            description="Access token issued",
            example=_TOKEN_EXAMPLE,
        ),
        status.HTTP_401_UNAUTHORIZED: error_response(
            description="Invalid credentials",
            detail="Invalid credentials",
        ),
    },
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    try:
        token = await asyncify(auth_service.authenticate)(
            form_data.username,
            form_data.password,
        )
    except InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return TokenResponse(access_token=token)
