"""
File: utils/populate_pilots.py
Rev: 1.0.1
Created: 2024-12-03
Last Modified: 2024-12-05
Changes:
- Updated paths and imports to match new structure
- Added project root to Python path
"""
import os
import sys

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from flask import Flask
from app.models import db, Teilnehmer
import sys

# Initialize Flask and SQLAlchemy
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/NRWCup2025.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Function to populate pilots
def populate_pilots():
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
        # Primarily Segler pilots
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
        ("Markus", True, False, True, False)
    ]

    print("Starting to populate pilots...")

    try:
        if '--force' in sys.argv:
            print("Clearing existing pilot data...")
            db.session.query(Teilnehmer).delete()
            db.session.commit()

        for name, is_segler, is_schlepper, is_punktwerter, is_wettkampfleitung in pilots_data:
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
        
        db.session.commit()
        print("\nSuccessfully populated pilot data!")
        return True

    except Exception as e:
        db.session.rollback()
        print(f"Error populating database: {e}")
        return False

if __name__ == '__main__':
    with app.app_context():
        if '--force' in sys.argv or Teilnehmer.query.count() == 0:
            populate_pilots()
        else:
            print("Database already contains pilots. Use --force to override.")