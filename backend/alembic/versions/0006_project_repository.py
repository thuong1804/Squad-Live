"""Store the local Git repository chosen for each project."""

import sqlalchemy as sa

from alembic import op

revision = "0006_project_repository"
down_revision = "0005_google_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("repository_path", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("projects", "repository_path")
