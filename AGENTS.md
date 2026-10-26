# FastAPI Best Practices for AI Agents

Extra rules for FastAPI work. They supplement the official FastAPI skill. Where that skill already decides a topic, follow it. This file only adds practices that the skill does not state.

Apply this file when writing or changing FastAPI application code.

## Project Structure

Organize by domain, not by file type. One package per bounded context.

```
src/
├── {domain}/           # e.g., auth/, posts/, aws/
│   ├── router.py       # API endpoints
│   ├── schemas.py      # Pydantic models
│   ├── models.py       # Persistence models
│   ├── service.py      # Business logic
│   ├── dependencies.py # Route dependencies
│   ├── config.py       # Domain-scoped BaseSettings
│   ├── constants.py    # Constants and error codes
│   ├── exceptions.py   # Domain-specific exceptions
│   └── utils.py        # Helper functions
├── config.py           # Global BaseSettings
├── models.py           # Shared Pydantic / persistence bases
├── exceptions.py       # Global exceptions
├── database.py         # Engine and session factory
└── main.py             # FastAPI app + lifespan
```

**Cross-domain imports**: always use the explicit module name. Never `from src.auth import` *.

```python
from src.auth import constants as auth_constants
from src.notifications import service as notification_service
from src.posts.constants import ErrorCode as PostsErrorCode
```

Import another domain at the package boundary (`from src.auth import service as auth_service`). Avoid deep paths such as `from src.auth.service.user import ...`.

## Async Routes

The official skill owns the async-versus-sync choice, including Asyncer when blocking and async code must mix. These are the extra constraints.

| Route does this                 | Use                                  |
| ------------------------------- | ------------------------------------ |
| CPU-bound work (>50 ms compute) | Offload to a worker process (Celery) |

### Threadpool caveats

- Default Starlette threadpool size is 40. Saturating it slows every sync route.
- Threads cost more than coroutines.
- A sync dependency runs in that threadpool. A small CPU-only check pays that overhead for no benefit.

### Files inside `async def`

Use an async file library such as `aiofiles`. A blocking `open()` inside `async def` stalls the event loop.

## Pydantic

### Use built-in validators

```python
from enum import StrEnum
from pydantic import AnyUrl, BaseModel, EmailStr, Field

class MusicBand(StrEnum):
    AEROSMITH = "AEROSMITH"
    QUEEN = "QUEEN"
    ACDC = "AC/DC"

class UserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    email: EmailStr
    age: int = Field(ge=18)                     # required, must be >= 18
    favorite_band: MusicBand | None = None
    website: AnyUrl | None = None
```

> **Don't** write `Field(ge=18, default=None)`. The constraint and the default contradict
> each other. Decide: required (`Field(ge=18)`) or optional (`int | None = Field(default=None, ge=18)`).

### Custom base model — modern serialization

`json_encoders` is deprecated in Pydantic v2. Use `@field_serializer` for per-field rules,
or annotate a custom type with `PlainSerializer`.

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, field_serializer

class CustomModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("*", when_used="json", check_fields=False)
    def _serialize_datetimes(self, value):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=ZoneInfo("UTC"))
            return value.strftime("%Y-%m-%dT%H:%M:%S%z")
        return value
```

Leave `ConfigDict(json_encoders=...)` unused.

### Split BaseSettings by domain

`pydantic-settings` is its own package since Pydantic v2. One `BaseSettings` subclass per domain. Reusing one `BaseSettings` for the whole app makes every domain read every variable.

```python
# src/auth/config.py
from datetime import timedelta
from pydantic_settings import BaseSettings, SettingsConfigDict

class AuthConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_", env_file=".env", extra="ignore")

    JWT_ALG: str
    JWT_SECRET: str
    JWT_EXP_MINUTES: int = 5
    REFRESH_TOKEN_KEY: str
    REFRESH_TOKEN_EXP: timedelta = timedelta(days=30)
    SECURE_COOKIES: bool = True

auth_settings = AuthConfig()
```

## Dependencies

The official skill owns `Annotated[..., Depends(...)]`, `yield` scopes, and router-level dependencies. These are the extra rules.

### Validate inside dependencies (not just inject)

```python
async def valid_post_id(post_id: UUID4) -> dict:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()
    return post
```

Chain a later check on that result when the route needs both:

```python
async def valid_owned_post(
    post: Annotated[dict, Depends(valid_post_id)],
    token_data: Annotated[dict, Depends(parse_jwt_data)],
) -> dict:
    if post["creator_id"] != token_data["user_id"]:
        raise UserNotOwner()
    return post
```

### Rules

- Dependencies are **cached per request**. Same `Depends(x)` called 5 times in one request → `x` runs once.
- Use **the same path-variable name** across endpoints when you want to share a dependency (e.g. `profile_id` in both `/profiles/{profile_id}` and `/creators/{profile_id}`).

## Authentication — JWT

Use **PyJWT**, not `python-jose` (unmaintained).

```python
import jwt  # PyJWT
from jwt.exceptions import InvalidTokenError

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except InvalidTokenError as exc:
        raise InvalidCredentials() from exc
```

## Database shape

Naming and query shape. The official skill chooses the ORM.

### Naming conventions

- `lower_case_snake`
- Singular tables: `post`, `user`, `post_like`
- Group with prefix: `payment_account`, `payment_bill`
- `_at` suffix for `datetime`, `_date` suffix for `date`
- Use the same FK column name everywhere it appears (`profile_id`, not `user_id` in some tables and `profile_id` in others)

### Index naming convention

Pass this dict as the metadata naming convention:

```python
POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}
```

### SQL-first, Pydantic-second

- Do joins, aggregation, and JSON shaping in SQL — Postgres is faster than CPython at this.
- Hydrate the result into Pydantic only for response validation, not for transformation.

## Background work — BackgroundTasks vs Celery

| Use BackgroundTasks when…                | Use Celery when…                             |
| ---------------------------------------- | -------------------------------------------- |
| Task is < 1 second                       | Task takes seconds to minutes                |
| Failure can be silently dropped          | You need retries, dead-letter, or visibility |
| Task is in-process (send email, log row) | Task is CPU-heavy or needs a separate pool   |
| You don't need scheduling                | You need cron, ETA, or rate limiting         |

```python
from fastapi import BackgroundTasks

@router.post("/signup")
async def signup(data: SignupIn, bg: BackgroundTasks):
    user = await service.create_user(data)
    bg.add_task(send_welcome_email, user.email)   # fire-and-forget, in-process
    return user
```

> BackgroundTasks run **after the response is sent, in the same worker process**. If the
> worker dies, the task is lost. There is no retry. Don't use them for anything you'd
> page on.

## Testing

### Async client from day one

```python
import pytest
from httpx import AsyncClient, ASGITransport

from src.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_create_post(client: AsyncClient):
    resp = await client.post("/posts", json={"title": "hi"})
    assert resp.status_code == 201
```

> **Don't** use `async_asgi_testclient` — it's unmaintained. The example above (httpx +
> `ASGITransport`) is the supported path.

### Override dependencies in tests

Don't monkeypatch internals. Use FastAPI's built-in `dependency_overrides`.

```python
from src.auth.dependencies import parse_jwt_data
from src.main import app

def fake_user():
    return {"user_id": "00000000-0000-0000-0000-000000000001"}

@pytest.fixture(autouse=True)
def _override_auth():
    app.dependency_overrides[parse_jwt_data] = fake_user
    yield
    app.dependency_overrides.clear()
```

## Migrations (Alembic)

- Migrations must be static and reversible.
- Use the async template: `alembic init -t async migrations`
- Descriptive filenames:

```ini
# alembic.ini
file_template = %%(year)d-%%(month).2d-%%(day).2d_%%(slug)s
```

→ `2026-04-14_add_post_content_idx.py`

## API documentation

### Hide docs outside selected envs

```python
from fastapi import FastAPI
from src.config import settings

SHOW_DOCS_IN = {"local", "staging"}
app_kwargs = {"title": "My API"}
if settings.ENVIRONMENT not in SHOW_DOCS_IN:
    app_kwargs["openapi_url"] = None    # disables /docs and /redoc

app = FastAPI(**app_kwargs)
```

### Document endpoints fully

Declare the public schema with the return type. Set `status_code`, `summary`, `description`, and a `responses` map for the error cases.

```python
from fastapi import APIRouter, status

router = APIRouter()

@router.post(
    "/items",
    status_code=status.HTTP_201_CREATED,
    summary="Create an item",
    description="Creates an item owned by the authenticated user.",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Validation error"},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse, "description": "Slug already exists"},
    },
)
async def create_item(payload: ItemCreate) -> ItemResponse: ...
```

Returning a Pydantic model and also setting `response_model=` to that same class builds the model twice (validate, then serialize). Trust the return type. Use `response_model` when the route returns a dict or a row and the public schema is a different type.

### Errors

Catch the specific exception class and raise `HTTPException` with a meaningful status. Catching `Exception` around a route body hides bugs and can turn 500s into silent 200s.

## Linting

```shell
ruff check --fix src
ruff format src
```

Add to a pre-commit hook or run in CI. Ruff replaces black + isort + autoflake + most of flake8.

## Anti-patterns

| Anti-pattern                                                                      | Why it's wrong                                       | Fix                                                                                                      |
| --------------------------------------------------------------------------------- | ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `open()` inside `async def`                                                       | Blocks the event loop.                               | Use `aiofiles`.                                                                                          |
| `from jose import jwt`                                                            | `python-jose` is unmaintained.                       | `import jwt` (PyJWT).                                                                                    |
| `from async_asgi_testclient import TestClient`                                    | Unmaintained.                                        | `httpx.AsyncClient` + `ASGITransport`.                                                                   |
| `model_config = ConfigDict(json_encoders={...})`                                  | Deprecated in Pydantic v2.                           | `@field_serializer` or `Annotated[T, PlainSerializer(...)]`.                                             |
| `Field(ge=18, default=None)`                                                      | Constraint contradicts the default.                  | Pick required or optional, not both.                                                                     |
| Catching `Exception` around a route's body                                        | Hides bugs and turns 500s into silent 200s.          | Catch the specific exception class; raise `HTTPException` with a meaningful status.                      |
| `BackgroundTasks` for anything you'd page on                                      | No retry, dies with the worker.                      | Use Celery.                                                                                              |
| Returning a Pydantic model and also setting `response_model=` to that same class  | Model gets constructed twice (validate + serialize). | Drop `response_model` and trust the return type, or return a dict/row and let `response_model` validate. |
| Importing across domains via deep paths (`from src.auth.service.user import ...`) | Tight coupling, hard to refactor.                    | `from src.auth import service as auth_service`.                                                          |
| Reusing one `BaseSettings` for the whole app                                      | Hard to reason about, every domain reads every var.  | One `BaseSettings` per domain.                                                                           |

## Quick reference

| Scenario                           | Solution                                       |
| ---------------------------------- | ---------------------------------------------- |
| CPU-intensive work                 | Celery worker process                          |
| Sync file I/O inside `async def`   | `aiofiles`                                     |
| Request validation against DB      | Dependency that loads + validates + returns    |
| Per-request dep caching            | Default behavior — same `Depends(x)` runs once |
| Share one dependency across routes | Same path-variable name (e.g. `profile_id`)    |
| Per-domain config                  | One `BaseSettings` subclass per domain         |
| Custom datetime serialization      | `@field_serializer`                            |
| Fire-and-forget short task         | `BackgroundTasks`                              |
| Reliable / scheduled / heavy task  | Celery                                         |
| JWT decode                         | PyJWT (`import jwt`)                           |
| HTTP test client                   | `httpx.AsyncClient` + `ASGITransport`          |
| Swap dep in tests                  | `app.dependency_overrides[dep] = fake`         |
| Lint + format                      | `ruff check --fix` + `ruff format`             |
| Docs outside local/staging         | `openapi_url=None`                             |
