"""
NRW Cup Scoring System - Database Setup v1.4
Location: setup_database.py

Worked 4 Dec @15:12 to create the database.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash
import os
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Date
from sqlalchemy.orm import relationship

# Initialize Flask app
app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/NRWCup2025.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Model definitions
class User(db.Model):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(20), unique=True, nullable=False)
    password = Column(String(60), nullable=False)
    role = Column(String(10), nullable=False)

class Location(db.Model):
    __tablename__ = 'locations'
    location_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    street = Column(String(50))
    city = Column(String(30))
    postal_code = Column(String(5))
    lat = Column(Float)
    lon = Column(Float)
    event_date = Column(Date, nullable=False)
    notes = Column(String(200))
    events = relationship("Event", backref="location")

class Event(db.Model):
    __tablename__ = 'events'
    event_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    location_id = Column(Integer, ForeignKey('locations.location_id'))
    status = Column(String(10), default='Pending')
    verein = Column(String(50), nullable=False)
    rounds = relationship("Round", backref="event")
    k_factors = relationship("EventKFactors", backref="event")

class TaskType(db.Model):
    __tablename__ = 'task_types'
    type_id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(30), nullable=False)
    name_de = Column(String(30), nullable=False)
    description = Column(String(200))
    score_type = Column(String(12), nullable=False)
    sort_order = Column(Integer)
    is_active = Column(Boolean, default=True)
    min_value = Column(Float)
    max_value = Column(Float)
    decimal_places = Column(Integer)
    allowed_values = Column(String(20))
    k_factors = relationship("EventKFactors", backref="task_type")

class EventKFactors(db.Model):
    __tablename__ = 'event_k_factors'
    k_factor_id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey('events.event_id'), nullable=False)
    task_type_id = Column(Integer, ForeignKey('task_types.type_id'), nullable=False)
    k_factor = Column(Integer, default=1)

class Teilnehmer(db.Model):
    __tablename__ = 'teilnehmer'
    teilnehmer_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    email = Column(String(30))
    handy = Column(String(15))
    verband = Column(String(20))
    verein = Column(String(50))
    versicherung_nummer = Column(String(20))
    kenntnisnachweiss = Column(String(20))
    laermpass = Column(Boolean, default=False)
    is_segler_pilot = Column(Boolean, default=False)
    is_schlepper_pilot = Column(Boolean, default=False)
    is_punktwerter = Column(Boolean, default=False)
    is_wettkampfleitung = Column(Boolean, default=False)
    scored_rounds = relationship("Score", backref="judge", foreign_keys="Score.judge_id")
    owned_aircraft = relationship("Flugzeuge", backref="owner", foreign_keys="Flugzeuge.plane_owner_id")
    piloted_aircraft = relationship("Flugzeuge", backref="pilot", foreign_keys="Flugzeuge.pilot_id")

class Flugzeuge(db.Model):
    __tablename__ = 'flugzeuge'
    flugzeug_id = Column(Integer, primary_key=True, autoincrement=True)
    is_segler = Column(Boolean, default=False)
    is_schlepper = Column(Boolean, default=False)
    name = Column(String(30), nullable=False)
    span = Column(Float)
    gewicht = Column(Float)
    antrieb = Column(String(30))
    prop = Column(String(30))
    fernsteuerung = Column(String(30))
    pilot_id = Column(Integer, ForeignKey('teilnehmer.teilnehmer_id'))
    plane_owner_id = Column(Integer, ForeignKey('teilnehmer.teilnehmer_id'))

class Team(db.Model):
    __tablename__ = 'teams'
    team_id = Column(Integer, primary_key=True, autoincrement=True)
    team_nummer = Column(Integer, nullable=False)
    schlepper_pilot_id = Column(Integer, ForeignKey('teilnehmer.teilnehmer_id'))
    segler_pilot_id = Column(Integer, ForeignKey('teilnehmer.teilnehmer_id'))
    schlepper_flugzeug_id = Column(Integer, ForeignKey('flugzeuge.flugzeug_id'))
    segler_flugzeug_id = Column(Integer, ForeignKey('flugzeuge.flugzeug_id'))
    schlepper_pilot = relationship("Teilnehmer", foreign_keys=[schlepper_pilot_id])
    segler_pilot = relationship("Teilnehmer", foreign_keys=[segler_pilot_id])
    schlepper_flugzeug = relationship("Flugzeuge", foreign_keys=[schlepper_flugzeug_id])
    segler_flugzeug = relationship("Flugzeuge", foreign_keys=[segler_flugzeug_id])
    team_rounds = relationship("TeamRound", backref="team")

class Round(db.Model):
    __tablename__ = 'rounds'
    round_id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey('events.event_id'))
    round_number = Column(Integer, nullable=False)
    status = Column(String(10), default='Active')
    weather_notes = Column(String(200))
    team_rounds = relationship("TeamRound", backref="round")

class TeamRound(db.Model):
    __tablename__ = 'team_rounds'
    team_round_id = Column(Integer, primary_key=True, autoincrement=True)
    round_id = Column(Integer, ForeignKey('rounds.round_id'))
    team_id = Column(Integer, ForeignKey('teams.team_id'))
    start_order = Column(Integer)
    status = Column(String(10), default='Pending')

class Score(db.Model):
    __tablename__ = 'scores'
    score_id = Column(Integer, primary_key=True, autoincrement=True)
    team_round_id = Column(Integer, ForeignKey('team_rounds.team_round_id'))
    judge_id = Column(Integer, ForeignKey('teilnehmer.teilnehmer_id'))
    bodenstart_schleppzug = Column(Float)
    platzuberflug = Column(Float)
    ausklinken = Column(Float)
    verfahrenskurve = Column(Float)
    seilabwurf = Column(Float)
    hohe_kurve = Column(Float)
    landeanflug_motor = Column(Float)
    landung_motor = Column(Float)
    landeanflug_segler = Column(Float)
    landung_segler = Column(Float)
    erscheinungsbild = Column(Float)
    zielabwurf_schleppseil = Column(Integer)
    landegenauigkeit_motor = Column(Integer)
    landegenauigkeit_segler = Column(Integer)
    touch_and_go = Column(Integer)
    seglerzeit = Column(Integer)
    entered_at = Column(DateTime, default=datetime.utcnow)
    entered_by = Column(Integer, ForeignKey('users.user_id'))
    notes = Column(Text)
    vermerk = Column(Text)
    validations = relationship("ScoreValidation", backref="score")
    entered_by_user = relationship("User", foreign_keys=[entered_by])

class ScoreValidation(db.Model):
    __tablename__ = 'score_validations'
    validation_id = Column(Integer, primary_key=True, autoincrement=True)
    score_id = Column(Integer, ForeignKey('scores.score_id'))
    entry_user_id = Column(Integer, ForeignKey('users.user_id'))
    validation_status = Column(String(10), default='Pending')
    entered_at = Column(DateTime, default=datetime.utcnow)
    resolved_by = Column(Integer, ForeignKey('users.user_id'))
    resolved_at = Column(DateTime)
    resolution_notes = Column(String(200))
    entry_user = relationship("User", foreign_keys=[entry_user_id])
    resolver = relationship("User", foreign_keys=[resolved_by])

class AuditLog(db.Model):
    __tablename__ = 'auditlog'
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String(50))
    record_id = Column(Integer)
    field_changed = Column(String(100))
    old_value = Column(String(200))
    new_value = Column(String(200))
    changed_by = Column(Integer, ForeignKey('users.user_id'))
    changed_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", foreign_keys=[changed_by])

def init_db():
    """Initialize database and create admin user"""
    try:
        # Create instance directory if it doesn't exist
        os.makedirs('instance', exist_ok=True)
        
        # Create all tables
        with app.app_context():
            db.create_all()
            print("Database tables created successfully.")

            # Create admin user if it doesn't exist
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                admin = User(
                    username='admin',
                    password=generate_password_hash('admin123', method='pbkdf2:sha256'),
                    role='Admin'
                )
                db.session.add(admin)
                
                # Add a test location
                test_location = Location(
                    name='Bocholt',
                    city='Bocholt',
                    postal_code='46395',
                    event_date=datetime.strptime('2025-05-01', '%Y-%m-%d').date()
                )
                db.session.add(test_location)
                
                db.session.commit()
                print("Admin user created (username: admin, password: admin123)")
                print("Test location added.")

            # Verify tables were created
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print("\nCreated tables:")
            for table in tables:
                print(f"- {table}")
                
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

if __name__ == '__main__':
    init_db()