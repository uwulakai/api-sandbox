"""Baseline for databases created before migrations were introduced."""

from alembic import op
import sqlalchemy as sa


revision = "0001_baseline"
down_revision = None

core_tables = {"users", "sessions", "mocks", "mock_endpoints"}


def timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    existing = core_tables & set(sa.inspect(op.get_bind()).get_table_names())
    if existing == core_tables:
        return
    if existing:
        raise RuntimeError("Incomplete legacy API Sandbox schema")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"], unique=True)
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_table(
        "mocks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("desired_status", sa.Enum("STOPPED", "RUNNING", name="mockdesiredstatus"), nullable=False),
        sa.Column(
            "runtime_status",
            sa.Enum("PENDING", "STARTING", "RUNNING", "STOPPING", "STOPPED", "ERROR", name="mockruntimestatus"),
            nullable=False,
        ),
        sa.Column("deletion_requested", sa.Boolean(), nullable=False),
        sa.Column("container_id", sa.String(128)),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(2000)),
        *timestamps(),
    )
    op.create_index("ix_mocks_owner_id", "mocks", ["owner_id"])
    op.create_table(
        "mock_endpoints",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("mock_id", sa.String(), sa.ForeignKey("mocks.id"), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(2048), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_headers", sa.JSON(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("delay_ms", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("mock_id", "method", "path", name="uq_mock_endpoint_method_path"),
    )
    op.create_index("ix_mock_endpoints_method", "mock_endpoints", ["method"])
    op.create_index("ix_mock_endpoints_mock_id", "mock_endpoints", ["mock_id"])


def downgrade() -> None:
    raise RuntimeError("The baseline may contain preexisting tables and cannot be downgraded")
