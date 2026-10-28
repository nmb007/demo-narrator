"""Auth FastAPI dependencies."""

from typing import Annotated

from asyncer import asyncify
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from src.auth import service as auth_service
from src.auth.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    return await asyncify(auth_service.get_user_from_token)(token)


CurrentUserDep = Annotated[User, Depends(get_current_user)]
