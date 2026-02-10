"""
File: utils/initialize_database.py
Version: 1.0.0
Created: 2024-12-05
Description: Initialize database with all models and basic task types
"""

import os
import sys

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from flask import Flask
from app.models import (
    db, User, TaskType, Teilnehmer, Flugzeuge, Team, Round, 
    TeamRound, Score, AuditLog, Location, Event, EventKFactors
)
from werkzeug.security import generate_password_hash
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/NRWCup2025.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

def init_db():
    """Initialize database with tables and basic data"""
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
                print("Admin user created (username: admin, password: admin123)")

            # Create basic task types
            tasks = [
                {
                    'code': 'START',
                    'name': 'Ground Start',
                    'name_de': 'Bodenstart Schleppzug',
                    'score_type': 'float',
                    'min_value': 0.0,
                    'max_value': 10.0,
                    'decimal_places': 1,
                    'sort_order': 1
                },
                {
                    'code': 'PLTZU',
                    'name': 'Field Circuit',
                    'name_de': 'Platzüberflug',
                    'score_type': 'float',
                    'min_value': 0.0,
                    'max_value': 10.0,
                    'decimal_places': 1,
                    'sort_order': 2
                },
                {
                    'code': 'AUSKL',
                    'name': 'Release',
                    'name_de': 'Ausklinken',
                    'score_type': 'float',
                    'min_value': 0.0,
                    'max_value': 10.0,
                    'decimal_places': 1,
                    'sort_order': 3
                },
                {
                    'code': 'VKURV',
                    'name': 'Procedure Turn',
                    'name_de': 'Verfahrenskurve',
                    'score_type': 'float',
                    'min_value': 0.0,
                    'max_value': 10.0,
                    'decimal_places': 1,
                    'sort_order': 4
                },
                {
                    'code': 'SEILW',
                    'name': 'Rope Drop',
                    'name_de': 'Seilabwurf',
                    'score_type': 'float',
                    'min_value': 0.0,
                    'max_value': 10.0,
                    'decimal_places': 1,
                    'sort_order': 5
                },
                {
                    'code': 'HKURV',
                    'name': 'High Turn',
                    'name_de': 'Hohe Kurve',
                    'score_type': 'float',
                    'min_value': 0.0,
                    'max_value': 10.0,
                    'decimal_places': 1,
                    'sort_order': 6
                },
                {
                    'code': 'LANM',
                    'name': 'Landing Approach Motor',
                    'name_de': 'Landeanflug Motor',
                    'score_type': 'float',
                    'min_value': 0.0,
                    'max_value': 10.0,
                    'decimal_places': 1,
                    'sort_order': 7
                },
                {
                    'code': 'LANDM',
                    'name': 'Landing Motor',
                    'name_de': 'Landung Motor',
                    'score_type': 'float',
                    'min_value': 0.0,
                    'max_value': 10.0,
                    'decimal_places': 1,
                    'sort_order': 8
                },
                {
                    'code': 'LANS',
                    'name': 'Landing Approach Glider',
                    'name_de': 'Landeanflug Segler',
                    'score_type': 'float',
                    'min_value': 0.0,
                    'max_value': 10.0,
                    'decimal_places': 1,
                    'sort_order': 9
                },
                {
                    'code': 'LANDS',
                    'name': 'Landing Glider',
                    'name_de': 'Landung Segler',
                    'score_type': 'float',
                    'min_value': 0.0,
                    'max_value': 10.0,
                    'decimal_places': 1,
                    'sort_order': 10
                },
                {
                    'code': 'ERSCH',
                    'name': 'Overall Impression',
                    'name_de': 'Erscheinungsbild',
                    'score_type': 'float',
                    'min_value': 0.0,
                    'max_value': 10.0,
                    'decimal_places': 1,
                    'sort_order': 11
                },
                {
                    'code': 'SEILZ',
                    'name': 'Rope Target',
                    'name_de': 'Zielabwurf Schleppseil',
                    'score_type': 'integer',
                    'min_value': 0,
                    'max_value': 20,
                    'sort_order': 12
                },
                {
                    'code': 'LANDGM',
                    'name': 'Landing Accuracy Motor',
                    'name_de': 'Landegenauigkeit Motor',
                    'score_type': 'integer',
                    'min_value': 0,
                    'max_value': 20,
                    'sort_order': 13
                },
                {
                    'code': 'LANDGS',
                    'name': 'Landing Accuracy Glider',
                    'name_de': 'Landegenauigkeit Segler',
                    'score_type': 'integer',
                    'min_value': 0,
                    'max_value': 20,
                    'sort_order': 14
                },
                {
                    'code': 'TOUCH',
                    'name': 'Touch and Go',
                    'name_de': 'Touch and Go',
                    'score_type': 'integer',
                    'min_value': 0,
                    'max_value': 1,
                    'sort_order': 15
                }
            ]

            # Add tasks if they don't exist
            for task_data in tasks:
                if not TaskType.query.filter_by(code=task_data['code']).first():
                    task = TaskType(**task_data)
                    db.session.add(task)
                    print(f"Added task type: {task_data['name_de']}")

            # Add pilots if they don't exist
            pilots_data = [
                # (name, is_segler_pilot, is_schlepper_pilot, is_punktwerter, is_wettkampfleitung)
                ("Kees Blokland", True, True, True, True),
                ("Uli Hunschok", False, True, True, False),
                ("Rafael Rybski", True, True, True, False),
                ("Burkhard Wagner", False, True, True, False),
                ("Markus Fetsch", False, True, True, False),
                ("Sven Steinweg", False, True, True, False),
                ("Hajo Willems", False, True, True, False),
                ("Harald Sieben", False, True, True, False),
                ("Christoph Fackeldey", True, True, True, False),
                ("Dietmar Reichel", False, True, True, False),
                ("Andreas Rybski", False, True, True, False),
                ("Ulf Reichmann", False, True, True, False),
                ("Ralf Doll", True, True, True, False),
                ("Hartmut Schuermann", False, True, True, False),
                ("Marcel Rybski", True, False, True, False),
                ("Stefan Eyssen", True, False, True, False),
                ("Klaus-Peter Müller", True, False, True, False),
                ("Stephan Weitz", True, False, True, False),
                ("Michael Bremen", True, False, True, False),
                ("Ingo von der Forst", True, False, True, False),
                ("Fabius Fackeldey", True, False, True, False),
                ("Thomas Schelinski", True, False, True, False),
                ("Dominik Braun", True, False, True, False),
                ("Claus-Jürgen Grobe", True, False, True, False),
                ("Frank Grünter", True, False, True, False),
                ("Ralf Wunder", True, False, True, False),
                ("Markus Böhm", True, False, True, False),
            ]

            # Add pilots
            for name, is_segler, is_schlepper, is_punktwerter, is_wettkampfleitung in pilots_data:
                if not Teilnehmer.query.filter_by(name=name).first():
                    pilot = Teilnehmer(
                        name=name,
                        is_segler_pilot=is_segler,
                        is_schlepper_pilot=is_schlepper,
                        is_punktwerter=is_punktwerter,
                        is_wettkampfleitung=is_wettkampfleitung,
                        verband="DMFV"  # Default value
                    )
                    db.session.add(pilot)
                    print(f"Added pilot: {name}")

            # Add test location
            test_location = Location(
                name='Bocholt',
                city='Bocholt',
                postal_code='46395',
                event_date=datetime.strptime('2025-05-01', '%Y-%m-%d').date()
            )
            db.session.add(test_location)
            print("Added test location: Bocholt")

            db.session.commit()
            print("\nDatabase initialization complete!")

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