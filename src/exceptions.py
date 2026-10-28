"""Global application exceptions."""


class AppError(Exception):
    """Base application error."""


class NotFoundError(AppError):
    """Requested resource was not found."""


class ForbiddenError(AppError):
    """Caller is not allowed to access the resource."""


class ConflictError(AppError):
    """Request conflicts with current state."""
