"""Initial schema baseline.

Revision ID: 001
Revises: None
Create Date: 2025-01-01 00:00:00.000000

This is the baseline migration capturing the existing schema.
All tables already exist in production - this migration is for tracking only.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# Revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial tables if they don't exist.

    Note: Uses batch mode for SQLite ALTER TABLE support.
    """
    # ProcessingJob table
    op.create_table(
        "processingjob",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("project_filter", sa.String(), nullable=True),
        sa.Column("session_ids", sa.JSON(), nullable=True),
        sa.Column("total_sessions", sa.Integer(), nullable=False),
        sa.Column("processed_sessions", sa.Integer(), nullable=False),
        sa.Column("failed_sessions", sa.Integer(), nullable=False),
        sa.Column("entities_extracted", sa.Integer(), nullable=False),
        sa.Column("relationships_created", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )

    # APIKey table
    op.create_table(
        "apikey",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )

    # Create indexes
    op.create_index(
        "ix_processingjob_status",
        "processingjob",
        ["status"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_processingjob_created_at",
        "processingjob",
        ["created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_apikey_key_hash",
        "apikey",
        ["key_hash"],
        unique=True,
        if_not_exists=True,
    )


def downgrade() -> None:
    """Drop all tables.

    WARNING: This will delete all data!
    """
    op.drop_index("ix_apikey_key_hash", table_name="apikey")
    op.drop_index("ix_processingjob_created_at", table_name="processingjob")
    op.drop_index("ix_processingjob_status", table_name="processingjob")
    op.drop_table("apikey")
    op.drop_table("processingjob")
