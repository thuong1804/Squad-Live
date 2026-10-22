"""Versioned review sessions and immutable review artifacts; retain v1 snapshots."""

import sqlalchemy as sa

from alembic import op

revision = "0002_review_revisions"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("workflow_runs") as batch:
        batch.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(
            sa.Column("repair_count", sa.Integer(), nullable=False, server_default="0")
        )
        for name, size in [("failed_step", 40), ("gate_id", 36), ("gate_artifact_id", 36)]:
            batch.add_column(sa.Column(name, sa.String(size)))
    convention = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
    old_unique = next(
        c["name"]
        for c in sa.inspect(op.get_bind()).get_unique_constraints("approvals")
        if c["column_names"] == ["run_id", "step", "attempt"]
    )
    with op.batch_alter_table("approvals", naming_convention=convention) as batch:
        batch.drop_constraint(old_unique or "uq_approvals_run_id", type_="unique")
        batch.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
        for name, size in [("gate_id", 36), ("artifact_id", 36), ("return_to", 40)]:
            batch.add_column(sa.Column(name, sa.String(size)))
        batch.create_unique_constraint(
            "uq_approval_revision", ["run_id", "step", "attempt", "revision"]
        )
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("workflow_runs.id"), nullable=False),
        sa.Column("gate_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.UniqueConstraint("run_id", "gate_id"),
    )
    op.create_index("ix_artifacts_run_id", "artifacts", ["run_id"])


def downgrade():
    # Multiple review revisions cannot be represented by the v1 unique key.
    connection = op.get_bind()
    duplicate = connection.execute(
        sa.text("SELECT 1 FROM approvals GROUP BY run_id, step, attempt HAVING COUNT(*) > 1")
    ).first()
    if duplicate:
        raise RuntimeError("Cannot downgrade: review revisions would lose history")
    op.drop_table("artifacts")
    with op.batch_alter_table("approvals") as batch:
        batch.drop_constraint("uq_approval_revision", type_="unique")
        for name in ("revision", "gate_id", "artifact_id", "return_to"):
            batch.drop_column(name)
        batch.create_unique_constraint("uq_approvals_run_id", ["run_id", "step", "attempt"])
    with op.batch_alter_table("workflow_runs") as batch:
        for name in ("revision", "repair_count", "failed_step", "gate_id", "gate_artifact_id"):
            batch.drop_column(name)
