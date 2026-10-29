"""API integration tests for auth endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_201(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/signup",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "user@example.com"
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_signup_409_duplicate_email(client: AsyncClient) -> None:
    payload = {"email": "dup@example.com", "password": "password123"}
    assert (await client.post("/v1/auth/signup", json=payload)).status_code == 201
    duplicate = await client.post("/v1/auth/signup", json=payload)
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_signup_422_invalid_payload(client: AsyncClient) -> None:
    bad_email = await client.post(
        "/v1/auth/signup",
        json={"email": "not-an-email", "password": "password123"},
    )
    assert bad_email.status_code == 422

    short_password = await client.post(
        "/v1/auth/signup",
        json={"email": "ok@example.com", "password": "short"},
    )
    assert short_password.status_code == 422


@pytest.mark.asyncio
async def test_login_200(client: AsyncClient) -> None:
    await client.post(
        "/v1/auth/signup",
        json={"email": "login@example.com", "password": "password123"},
    )
    response = await client.post(
        "/v1/auth/login",
        data={"username": "login@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


@pytest.mark.asyncio
async def test_login_401_bad_credentials(client: AsyncClient) -> None:
    await client.post(
        "/v1/auth/signup",
        json={"email": "badlogin@example.com", "password": "password123"},
    )
    wrong = await client.post(
        "/v1/auth/login",
        data={"username": "badlogin@example.com", "password": "wrong-password"},
    )
    assert wrong.status_code == 401

    missing_user = await client.post(
        "/v1/auth/login",
        data={"username": "nobody@example.com", "password": "password123"},
    )
    assert missing_user.status_code == 401


@pytest.mark.asyncio
async def test_login_422_missing_fields(client: AsyncClient) -> None:
    response = await client.post("/v1/auth/login", data={})
    assert response.status_code == 422
