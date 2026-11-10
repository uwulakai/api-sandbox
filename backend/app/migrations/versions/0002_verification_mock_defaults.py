"""Store pending registrations, Mock defaults and endpoint metadata."""

from alembic import op
import sqlalchemy as sa


revision = "0002_verification_mock_defaults"
down_revision = "0001_baseline"


def upgrade() -> None:
    op.create_table(
        "email_verifications",
        sa.Column("email", sa.String(320), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resend_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_email_verifications_expires_at", "email_verifications", ["expires_at"])
    op.add_column("mocks", sa.Column("default_response_headers", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("mocks", sa.Column("default_delay_ms", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("mock_endpoints", sa.Column("name", sa.String(120)))
    op.add_column("mock_endpoints", sa.Column("description", sa.String(500)))


def downgrade() -> None:
    op.drop_column("mock_endpoints", "description")
    op.drop_column("mock_endpoints", "name")
    op.drop_column("mocks", "default_delay_ms")
    op.drop_column("mocks", "default_response_headers")
    op.drop_table("email_verifications")
