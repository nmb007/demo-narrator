"""FastAPI application entrypoint."""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.auth.router import router as auth_router
from src.config import cors_allow_origins, settings
from src.narration.router import router as narration_router

SHOW_DOCS_IN = {"local", "staging"}

app_kwargs: dict = {"title": "Demo Narrator API", "version": "0.1.0"}
if settings.ENVIRONMENT not in SHOW_DOCS_IN:
    app_kwargs["openapi_url"] = None

app = FastAPI(**app_kwargs)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
    max_age=600,
)

api_v1 = APIRouter(prefix="/v1")
api_v1.include_router(auth_router)
api_v1.include_router(narration_router)
app.include_router(api_v1)


@app.get(
    "/health",
    summary="Health check",
    responses={
        200: {
            "description": "Service is up",
            "content": {
                "application/json": {
                    "example": {"status": "ok"},
                }
            },
        }
    },
)
def health() -> dict[str, str]:
    return {"status": "ok"}
