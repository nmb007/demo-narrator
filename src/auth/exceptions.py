"""Auth domain exceptions."""

from src.exceptions import AppError, ConflictError


class InvalidCredentials(AppError):
    """Email or password is incorrect."""


class EmailAlreadyRegistered(ConflictError):
    """A user with this email already exists."""
