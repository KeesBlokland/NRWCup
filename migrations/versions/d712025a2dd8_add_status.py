"""Add status column to teams table

Revision ID: d712025a2dd8
Revises: 
Create Date: 2025-01-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd712025a2dd8'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('teams') as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(10), nullable=False, server_default='active'))
    
def downgrade():
    with op.batch_alter_table('teams') as batch_op:
        batch_op.drop_column('status')