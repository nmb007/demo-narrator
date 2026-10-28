"""Shared API schemas."""

from typing import Any

from fastapi import status
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard HTTP error body returned by FastAPI ``HTTPException``."""

    detail: str = Field(description="Human-readable error message")


def success_response(
    *,
    model: type[BaseModel],
    description: str,
    example: dict[str, Any],
) -> dict:
    """OpenAPI success response with schema model and a sample JSON body."""
    return {
        "model": model,
        "description": description,
        "content": {
            "application/json": {
                "example": example,
            }
        },
    }


def error_response(
    *,
    description: str,
    detail: str | None = None,
    examples: dict[str, dict] | None = None,
) -> dict:
    """OpenAPI response entry with ``ErrorResponse`` schema and sample body(ies).

    Pass ``detail`` for a single example, or ``examples`` as
    ``{name: {"summary": "...", "value": {"detail": "..."}}}``.
    """
    content: dict = {}
    if examples is not None:
        content["examples"] = examples
    elif detail is not None:
        content["example"] = {"detail": detail}
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {"application/json": content},
    }


def error_responses(**entries: tuple[str, str]) -> dict:
    """Build a ``responses`` map from ``HTTP_<code>=(description, detail)`` kwargs.

    Example::

        error_responses(
            HTTP_404_NOT_FOUND=("Video not found", "Video not found"),
        )
    """
    out: dict = {}
    for name, (description, detail) in entries.items():
        code = getattr(status, name)
        out[code] = error_response(description=description, detail=detail)
    return out


NOT_AUTHENTICATED_RESPONSE: dict = error_responses(
    HTTP_401_UNAUTHORIZED=(
        "Missing or invalid access token",
        "Not authenticated",
    ),
)
