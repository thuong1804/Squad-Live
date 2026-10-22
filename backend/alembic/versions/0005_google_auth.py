"""Google identities, one-time OAuth state, revocable browser sessions."""

import sqlalchemy as sa

from alembic import op

revision = "0005_google_auth"
down_revision = "0004_ai_connections"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "google_accounts",
        sa.Column("subject", sa.String(100), primary_key=True),
        sa.Column("identity", sa.String(200), unique=True, nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "login_attempts",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("browser_hash", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(128), nullable=False),
        sa.Column("verifier", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_login_attempts_expires_at", "login_attempts", ["expires_at"])
    op.create_table(
        "pm_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "subject", sa.String(100), sa.ForeignKey("google_accounts.subject"), nullable=False
        ),
        sa.Column("csrf_token", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pm_sessions_subject", "pm_sessions", ["subject"])
    op.create_index("ix_pm_sessions_expires_at", "pm_sessions", ["expires_at"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM google_accounts")):
        raise RuntimeError("Downgrade would lose Google identity history")
    op.drop_table("pm_sessions")
    op.drop_table("login_attempts")
    op.drop_table("google_accounts")
