"""Pin an isolated local Git worktree to a workflow run."""

import sqlalchemy as sa

from alembic import op

revision = "0007_run_workspaces"
down_revision = "0006_project_repository"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "run_workspaces",
        sa.Column("run_id", sa.String(36), sa.ForeignKey("workflow_runs.id"), primary_key=True),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("worktree_path", sa.Text(), nullable=False, unique=True),
        sa.Column("base_commit", sa.String(40), nullable=False),
        sa.Column("base_branch", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM run_workspaces")):
        raise RuntimeError("Downgrade would orphan local Git worktrees")
    op.drop_table("run_workspaces")
