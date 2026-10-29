"""Auth request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "email": "you@example.com",
                    "created_at": "2026-01-15T12:00:00Z",
                }
            ]
        }
    )

    id: UUID
    email: EmailStr
    created_at: datetime


class TokenResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                }
            ]
        }
    )

    access_token: str
    token_type: str = "bearer"
