"""Reset alembic version

Revision ID: cleanup_01
Revises: d712025a2dd8
Create Date: 2025-01-24
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'cleanup_01' 
down_revision = 'd712025a2dd8'
branch_labels = None
depends_on = None

def upgrade():
    # Reset alembic version to latest
    op.execute('DELETE FROM alembic_version')
    op.execute("INSERT INTO alembic_version (version_num) VALUES ('cleanup_01')")

def downgrade():
    op.execute('DELETE FROM alembic_version')
    op.execute("INSERT INTO alembic_version (version_num) VALUES ('d712025a2dd8')")