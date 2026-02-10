"""Add score locking fields

Revision ID: d56cffcc520c
Revises: 6879a339a318
Create Date: 2025-05-04 16:22:48.904414

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd56cffcc520c'
down_revision = '6879a339a318'
branch_labels = None
depends_on = None



def upgrade():
    with op.batch_alter_table('scores', schema=None) as batch_op:
        batch_op.add_column(sa.Column('locked', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('locked_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('locked_by', sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table('scores', schema=None) as batch_op:
        batch_op.drop_column('locked_by')
        batch_op.drop_column('locked_at')
        batch_op.drop_column('locked')