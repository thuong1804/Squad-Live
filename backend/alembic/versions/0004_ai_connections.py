"""Encrypted owner-scoped BYOK connections."""

import sqlalchemy as sa

from alembic import op

revision = "0004_ai_connections"
down_revision = "0003_ba_agent"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner", sa.String(200), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_ai_connections_owner", "ai_connections", ["owner"])
    for table in ("workflow_runs", "agent_runs"):
        op.add_column(table, sa.Column("connection_id", sa.String(36), nullable=True))


def downgrade():
    db = op.get_bind()
    if db.scalar(sa.text("SELECT count(*) FROM ai_connections")):
        raise RuntimeError("Downgrade would lose AI connection history")
    for table in ("agent_runs", "workflow_runs"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("connection_id")
    op.drop_index("ix_ai_connections_owner", table_name="ai_connections")
    op.drop_table("ai_connections")
