"""
File: migrations/versions/create_score_values.py
Version: 1.0.0
Created: 2025-02-28
Description: Migration script to create ScoreValue table and migrate existing data
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

# revision identifiers
revision = 'create_score_values'
down_revision = None
branch_labels = None
depends_on = None

Base = declarative_base()

# Define models for data migration
class Score(Base):
    __tablename__ = 'scores'
    score_id = sa.Column(sa.Integer, primary_key=True)
    team_round_id = sa.Column(sa.Integer)
    judge_id = sa.Column(sa.Integer)
    bodenstart_schleppzug = sa.Column(sa.Float)
    platzuberflug = sa.Column(sa.Float)
    ausklinken = sa.Column(sa.Float)
    verfahrenskurve = sa.Column(sa.Float)
    seilabwurf = sa.Column(sa.Float)
    hohe_kurve = sa.Column(sa.Float)
    landeanflug_motor = sa.Column(sa.Float)
    landung_motor = sa.Column(sa.Float)
    landeanflug_segler = sa.Column(sa.Float)
    landung_segler = sa.Column(sa.Float)
    erscheinungsbild = sa.Column(sa.Float)
    zielabwurf_schleppseil = sa.Column(sa.Integer)
    landegenauigkeit_motor = sa.Column(sa.Integer)
    landegenauigkeit_segler = sa.Column(sa.Integer)
    seglerzeit = sa.Column(sa.Integer)

class TaskType(Base):
    __tablename__ = 'task_types'
    type_id = sa.Column(sa.Integer, primary_key=True)
    code = sa.Column(sa.String(20))
    score_type = sa.Column(sa.String(12))

class ScoreValue(Base):
    __tablename__ = 'score_values'
    value_id = sa.Column(sa.Integer, primary_key=True)
    score_id = sa.Column(sa.Integer, sa.ForeignKey('scores.score_id'))
    task_type_id = sa.Column(sa.Integer, sa.ForeignKey('task_types.type_id'))
    value = sa.Column(sa.Float)

def upgrade():
    # Create new score_values table
    op.create_table('score_values',
        sa.Column('value_id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('score_id', sa.Integer(), nullable=False),
        sa.Column('task_type_id', sa.Integer(), nullable=False),
        sa.Column('value', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['score_id'], ['scores.score_id'], ),
        sa.ForeignKeyConstraint(['task_type_id'], ['task_types.type_id'], ),
        sa.PrimaryKeyConstraint('value_id')
    )
    
    # Create index for performance
    op.create_index('idx_score_task_lookup', 'score_values', ['score_id', 'task_type_id'], unique=False)
    
    # Migrate existing data
    bind = op.get_bind()
    session = Session(bind=bind)
    
    # Map from field names to task type codes
    field_to_code_map = {
        'bodenstart_schleppzug': 'STRT',
        'platzuberflug': 'PLTZU', 
        'ausklinken': 'AUSKL',
        'verfahrenskurve': 'VKURV',
        'seilabwurf': 'SEILW',
        'hohe_kurve': 'HKURV',
        'landeanflug_motor': 'LANM',
        'landung_motor': 'LANDM',
        'landeanflug_segler': 'LANDGS',
        'landung_segler': 'LANDS',
        'erscheinungsbild': 'ERSCH',
        'zielabwurf_schleppseil': 'SEILZ',
        'landegenauigkeit_motor': 'LANDGM',
        'landegenauigkeit_segler': 'LANS',
        'seglerzeit': 'SEGZEIT'
    }
    
    try:
        # Get all existing scores
        scores = session.query(Score).all()
        
        # Get task types by code
        task_types = {tt.code: tt.type_id for tt in session.query(TaskType).all()}
        
        # Migrate each score
        for score in scores:
            for field_name, code in field_to_code_map.items():
                # Get the value from the score
                value = getattr(score, field_name)
                
                # Only create score_value entries for non-null values
                if value is not None and code in task_types:
                    score_value = ScoreValue(
                        score_id=score.score_id,
                        task_type_id=task_types[code],
                        value=value
                    )
                    session.add(score_value)
        
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def downgrade():
    # Simply drop the table (data will be lost)
    op.drop_index('idx_score_task_lookup', table_name='score_values')
    op.drop_table('score_values')