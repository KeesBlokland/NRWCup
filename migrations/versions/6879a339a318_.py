"""empty message

Revision ID: 6879a339a318
Revises: cleanup_01, create_score_values
Create Date: 2025-02-28 18:40:05.172636

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6879a339a318'
down_revision = ('cleanup_01', 'create_score_values')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
