"""Durable BA execution leases and provider usage; no secrets or prompt bodies."""

import sqlalchemy as sa

from alembic import op

revision = "0003_ba_agent"
down_revision = "0002_review_revisions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("workflow_runs.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("prompt_version", sa.String(60), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("context_chars", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(60)),
        sa.Column("artifact_id", sa.String(36)),
        sa.UniqueConstraint("run_id", "role", "attempt", "revision"),
    )
    op.create_index("ix_agent_runs_run_id", "agent_runs", ["run_id"])
    op.create_index("ix_agent_runs_lease_expires_at", "agent_runs", ["lease_expires_at"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT 1 FROM agent_runs LIMIT 1")).first():
        raise RuntimeError("Cannot downgrade: BA execution history would be lost")
    op.drop_table("agent_runs")
