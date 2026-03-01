"""
File: app/models.py
Version: 2.0.0
Created: 2025-04-05
Description: Simplified database models for NRW Cup 2025
"""

# app/models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import Index

db = SQLAlchemy()



class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(10), nullable=False)

class Teilnehmer(db.Model):
    __tablename__ = 'teilnehmer'
    teilnehmer_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), default="")
    handy = db.Column(db.String(20), default="")
    verband = db.Column(db.String(50), default="")
    verein = db.Column(db.String(100), default="")
    versicherung_nummer = db.Column(db.String(50), default="")
    kenntnisnachweiss = db.Column(db.String(50), default="")
    laermpass = db.Column(db.Boolean, default=False)
    is_segler_pilot = db.Column(db.Boolean, default=False)
    is_schlepper_pilot = db.Column(db.Boolean, default=False)
    is_punktwerter = db.Column(db.Boolean, default=False)
    is_wettkampfleitung = db.Column(db.Boolean, default=False)
    
    # Relationships
    judged_scores = db.relationship("Score", backref="judge", foreign_keys="Score.judge_id")
    owned_aircraft = db.relationship("Flugzeuge", backref="owner", foreign_keys="Flugzeuge.plane_owner_id")
    piloted_aircraft = db.relationship("Flugzeuge", backref="pilot", foreign_keys="Flugzeuge.pilot_id")

class Flugzeuge(db.Model):
    __tablename__ = 'flugzeuge'
    flugzeug_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    is_segler = db.Column(db.Boolean, default=False)
    is_schlepper = db.Column(db.Boolean, default=False)
    name = db.Column(db.String(30), nullable=False)
    span = db.Column(db.Float)
    gewicht = db.Column(db.Float)
    antrieb = db.Column(db.String(30))
    prop = db.Column(db.String(30))
    fernsteuerung = db.Column(db.String(30))
    pilot_id = db.Column(db.Integer, db.ForeignKey('teilnehmer.teilnehmer_id'))
    plane_owner_id = db.Column(db.Integer, db.ForeignKey('teilnehmer.teilnehmer_id'))

class Team(db.Model):
    __tablename__ = 'teams'
    team_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_nummer = db.Column(db.Integer, nullable=False)
    schlepper_pilot_id = db.Column(db.Integer, db.ForeignKey('teilnehmer.teilnehmer_id'))
    segler_pilot_id = db.Column(db.Integer, db.ForeignKey('teilnehmer.teilnehmer_id'))
    schlepper_flugzeug_id = db.Column(db.Integer, db.ForeignKey('flugzeuge.flugzeug_id'))
    segler_flugzeug_id = db.Column(db.Integer, db.ForeignKey('flugzeuge.flugzeug_id'))
    status = db.Column(db.String(10), nullable=False, default='active')  # 'active' or 'disabled'
    
    # Relationships
    schlepper_pilot = db.relationship("Teilnehmer", foreign_keys=[schlepper_pilot_id], backref="schlepper_teams")
    segler_pilot = db.relationship("Teilnehmer", foreign_keys=[segler_pilot_id], backref="segler_teams")
    schlepper_flugzeug = db.relationship("Flugzeuge", foreign_keys=[schlepper_flugzeug_id], backref="schlepper_teams")
    segler_flugzeug = db.relationship("Flugzeuge", foreign_keys=[segler_flugzeug_id], backref="segler_teams")
    team_rounds = db.relationship("TeamRound", backref="team", cascade="all, delete-orphan")

class Location(db.Model):
    __tablename__ = 'locations'
    location_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=True)
    street = db.Column(db.String(50))
    city = db.Column(db.String(30))
    postal_code = db.Column(db.String(5))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    notes = db.Column(db.String(200))
    
    # Relationships
    events = db.relationship("Event", backref="location")

class Event(db.Model):
    __tablename__ = 'events'
    event_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.location_id'))
    event_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), default='Pending')  # 'Pending', 'Active', 'Completed', 'Published'
    is_hidden = db.Column(db.Boolean, default=False)
    verein = db.Column(db.String(50), nullable=False)
    estimated_rounds = db.Column(db.Integer, default=4)
    
    # Relationships
    rounds = db.relationship("Round", backref="event", cascade="all, delete-orphan")

class Round(db.Model):
    __tablename__ = 'rounds'
    round_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.event_id'))
    round_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(10), default='Active')  # 'Active', 'Completed', 'Cancelled'
    
    # Relationships
    team_rounds = db.relationship("TeamRound", backref="round", cascade="all, delete-orphan")

class TeamRound(db.Model):
    __tablename__ = 'team_rounds'
    team_round_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    round_id = db.Column(db.Integer, db.ForeignKey('rounds.round_id'))
    team_id = db.Column(db.Integer, db.ForeignKey('teams.team_id'))
    start_order = db.Column(db.Integer)  # Used for ordering teams in a round
    status = db.Column(db.String(10), default='Pending')  # 'Pending', 'Completed', 'DNS', 'DNF'
    
    # Advanced fields for direct score access
    raw_score = db.Column(db.Float)  # Raw aggregate score (calculated)
    normalized_score = db.Column(db.Float)  # Normalized score (0-1000)
    rank = db.Column(db.Integer)  # Rank within this round
    is_dropped = db.Column(db.Boolean, default=False)  # If this round is dropped from final scoring
    
    # Relationships
    scores = db.relationship("Score", backref="team_round", cascade="all, delete-orphan")

class TaskType(db.Model):
    __tablename__ = 'task_types'
    type_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(20), unique=True, nullable=False)  
    name = db.Column(db.String(30), nullable=False)  
    name_de = db.Column(db.String(30), nullable=False)  
    description = db.Column(db.String(200))  
    score_type = db.Column(db.String(12), nullable=False)  # 'float', 'integer', 'enum'
    sort_order = db.Column(db.Integer)  
    is_active = db.Column(db.Boolean, default=True)
    min_value = db.Column(db.Float)  
    max_value = db.Column(db.Float)  
    decimal_places = db.Column(db.Integer)  
    allowed_values = db.Column(db.String(20))  # Comma-separated values for enums
    k_factor = db.Column(db.Integer, default=1)  # Multiplier for the task's score

class Score(db.Model):
    __tablename__ = 'scores'
    score_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_round_id = db.Column(db.Integer, db.ForeignKey('team_rounds.team_round_id'))
    judge_id = db.Column(db.Integer, db.ForeignKey('teilnehmer.teilnehmer_id'))
    entered_at = db.Column(db.DateTime, default=datetime.utcnow)
    entered_by = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    notes = db.Column(db.Text)
    vermerk = db.Column(db.Text)
    
    locked = db.Column(db.Boolean, default=False)
    locked_at = db.Column(db.DateTime)
    locked_by = db.Column(db.String(100))
    
    # Relationships
    values = db.relationship("ScoreValue", backref="score", cascade="all, delete-orphan")
    entered_by_user = db.relationship("User")

class ScoreValue(db.Model):
    __tablename__ = 'score_values'
    value_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    score_id = db.Column(db.Integer, db.ForeignKey('scores.score_id'), nullable=False)
    task_type_id = db.Column(db.Integer, db.ForeignKey('task_types.type_id'), nullable=False)
    value = db.Column(db.Float)
    
    # Relationships
    task_type = db.relationship("TaskType")
    
    # Add an index to improve query performance
    __table_args__ = (
        db.Index('idx_score_task_lookup', score_id, task_type_id),
    )

class SystemConfig(db.Model):
    __tablename__ = 'system_config'
    config_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    config_key = db.Column(db.String(50), unique=True, nullable=False)
    config_value = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AuditLog(db.Model):
    __tablename__ = 'auditlog'
    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    table_name = db.Column(db.String(50))
    record_id = db.Column(db.Integer)
    field_changed = db.Column(db.String(100))
    old_value = db.Column(db.String(200))
    new_value = db.Column(db.String(200))
    changed_by = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship("User")

class BugReport(db.Model):
    __tablename__ = 'bug_reports'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(10), default='new', nullable=False)  # new / done