"""Celery application."""

from celery import Celery

from src.config import settings

celery_app = Celery(
    "demo_narrator",
    broker=settings.CELERY_BROKER_URL,
    include=["src.narration.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
