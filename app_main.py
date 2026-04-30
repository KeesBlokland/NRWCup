"""
File: app_main.py
Version: 1.5.0
Created: 2025-01-19
Last Updated: 2026-02-10
Description: Main application entry point with streamlined blueprint registration
"""
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import os
import sys
import secrets
import logging
import importlib
from flask import Flask, render_template
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from app.models import db, SystemConfig, Event
from datetime import datetime
from app.utils.logger import DBLogger

sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')

# Database path - auto-detect based on project location
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'NRWCup2025.db')

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

# Initialize Flask app with correct template folder
template_dir = os.path.abspath(os.path.join(project_root, 'app', 'templates'))
static_dir = os.path.abspath(os.path.join(project_root, 'app', 'static'))

app = Flask(__name__,
           template_folder=template_dir,
           static_folder=static_dir)

# Configuration
from app.config import Config
app.config.from_object(Config)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ensure instance directory exists
instance_dir = os.path.dirname(db_path)
os.makedirs(instance_dir, exist_ok=True)
os.chmod(instance_dir, 0o775)

# Generate a secure secret key if one doesn't exist
secret_key_file = os.path.join(project_root, 'instance', 'secret_key')
if not os.path.exists(secret_key_file):
    os.makedirs(os.path.dirname(secret_key_file), exist_ok=True)
    with open(secret_key_file, 'wb') as f:
        f.write(secrets.token_urlsafe(32).encode())

# Load the secret key
with open(secret_key_file, 'rb') as f:
    app.config['SECRET_KEY'] = f.read()

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize the database with the app
db.init_app(app)
migrate = Migrate(app, db)

# Initialize database tables and config
with app.app_context():
    db.create_all()

    # Initialize logger configuration if it doesn't exist
    config = SystemConfig.query.filter_by(config_key='logging_enabled').first()
    if not config:
        config = SystemConfig(
            config_key='logging_enabled',
            config_value='true',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.session.add(config)
        db.session.commit()

    # Add is_hidden column to events table if not present (safe to run every startup)
    try:
        db.session.execute(db.text("ALTER TABLE events ADD COLUMN is_hidden BOOLEAN DEFAULT 0"))
        db.session.commit()
    except Exception:
        db.session.rollback()  # Column already exists — ignore

    # Add Messwerte columns to team_rounds if not present (#210)
    for col_def in [
        "mess_segzeit FLOAT",
        "mess_seilz INTEGER",
        "mess_landgm INTEGER",
        "mess_lans INTEGER",
    ]:
        try:
            db.session.execute(db.text(f"ALTER TABLE team_rounds ADD COLUMN {col_def}"))
            db.session.commit()
        except Exception:
            db.session.rollback()

    # Initialize drop-worst-round threshold if it doesn't exist
    drop_config = SystemConfig.query.filter_by(config_key='drop_worst_round_threshold').first()
    if not drop_config:
        drop_config = SystemConfig(
            config_key='drop_worst_round_threshold',
            config_value=str(Config.DROP_WORST_ROUND_THRESHOLD),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.session.add(drop_config)
        db.session.commit()

DBLogger.info("Application starting")

# Make current year and active event name available in all templates
@app.context_processor
def inject_globals():
    year = datetime.now().year
    try:
        event = Event.query.filter_by(status='Active').first()
        if not event:
            event = Event.query.filter_by(is_hidden=False).order_by(Event.event_date.desc()).first()
        active_event_name = event.name if event else f'NRW Cup {year}'
    except Exception:
        active_event_name = f'NRW Cup {year}'
    return {'current_year': year, 'active_event_name': active_event_name}

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500

# Register home route
@app.route('/')
def home():
    return render_template('home_main.html')

# Blueprint registration - each blueprint is tried individually
BLUEPRINTS = [
    ('app.routes.bp_teilnehmer', 'teilnehmer_bp', '/teilnehmer'),
    ('app.routes.bp_teams', 'teams_bp', '/teams'),
    ('app.routes.bp_contest', 'contest_bp', '/contest'),
    ('app.routes.bp_scoring', 'scoring_bp', '/scoring'),
    ('app.routes.bp_reports', 'reports_bp', '/reports'),
    ('app.routes.bp_system', 'system_bp', '/system'),
    ('app.routes.bp_flugzeuge', 'flugzeuge_bp', '/flugzeuge'),
    ('app.routes.bp_figures', 'figures_bp', '/figures'),
    ('app.routes.bp_formular', 'formular_bp', '/formular'),
    ('app.routes.bp_testdata', 'testdata_bp', '/testdata'),
    ('app.routes.bp_cleanup', 'cleanup_bp', '/cleanup'),
    ('app.routes.bp_start_order', 'start_order_bp', '/start_order'),
    ('app.routes.bp_bugreport', 'bugreport_bp', '/bugreport'),
]

registered = []
for module_path, bp_name, prefix in BLUEPRINTS:
    try:
        module = importlib.import_module(module_path)
        bp = getattr(module, bp_name)
        app.register_blueprint(bp, url_prefix=prefix)
        registered.append(bp_name)
    except Exception as e:
        print(f"Failed to register {bp_name}: {e}")

print(f"Registered {len(registered)}/{len(BLUEPRINTS)} blueprints: {', '.join(registered)}")

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode, threaded=True)
