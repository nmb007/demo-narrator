"""create user video narration_run

Revision ID: 20261027_0001
Revises:
Create Date: 2026-10-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261027_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("user_pkey")),
        sa.UniqueConstraint("email", name=op.f("user_email_key")),
    )
    op.create_index(op.f("email_idx"), "user", ["email"], unique=False)

    op.create_table(
        "video",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("source_ext", sa.String(length=8), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("video_user_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("video_pkey")),
    )
    op.create_index(op.f("user_id_idx"), "video", ["user_id"], unique=False)

    op.create_table(
        "narration_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_step", sa.String(length=32), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["video.id"],
            name=op.f("narration_run_video_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("narration_run_pkey")),
    )
    op.create_index(op.f("video_id_idx"), "narration_run", ["video_id"], unique=False)
    op.create_index(op.f("status_idx"), "narration_run", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("status_idx"), table_name="narration_run")
    op.drop_index(op.f("video_id_idx"), table_name="narration_run")
    op.drop_table("narration_run")
    op.drop_index(op.f("user_id_idx"), table_name="video")
    op.drop_table("video")
    op.drop_index(op.f("email_idx"), table_name="user")
    op.drop_table("user")
