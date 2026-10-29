"""Auth sync domain services."""

from uuid import UUID

from sqlmodel import Session, select

from src.auth.exceptions import EmailAlreadyRegistered, InvalidCredentials
from src.auth.models import User
from src.auth.utils import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from src.database import get_sync_session


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.exec(select(User).where(User.email == email)).first()


def get_user_by_id(session: Session, user_id: UUID) -> User | None:
    return session.get(User, user_id)


def signup(email: str, password: str) -> User:
    with get_sync_session() as session:
        if get_user_by_email(session, email):
            raise EmailAlreadyRegistered()
        user = User(email=email.lower(), hashed_password=hash_password(password))
        session.add(user)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user


def authenticate(email: str, password: str) -> str:
    with get_sync_session() as session:
        user = get_user_by_email(session, email.lower())
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentials()
        return create_access_token(user_id=user.id, email=user.email)


def get_user_from_token(token: str) -> User:
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise InvalidCredentials()
    with get_sync_session() as session:
        user = get_user_by_id(session, UUID(user_id))
        if user is None:
            raise InvalidCredentials()
        session.expunge(user)
        return user
