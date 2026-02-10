"""
File: app/routes/__init__.py
Version: 1.1.0
Created: 2024-12-05
Last Updated: 2025-04-16
Author: Claude
Description: Routes package initialization with added cleanup blueprint and removed start_order blueprint
"""

from .bp_teilnehmer import teilnehmer_bp
from .bp_teams import teams_bp
from .bp_contest import contest_bp
from .bp_scoring import scoring_bp
from .bp_reports import reports_bp
from .bp_system import system_bp
from .bp_flugzeuge import flugzeuge_bp
from .bp_figures import figures_bp
from .bp_formular import formular_bp
from .bp_testdata import testdata_bp
from .bp_cleanup import cleanup_bp

def init_routes(app):
    # Main routes at root level
    app.register_blueprint(teilnehmer_bp, url_prefix='/teilnehmer')
    app.register_blueprint(teams_bp, url_prefix='/teams') 
    app.register_blueprint(contest_bp, url_prefix='/contest')
    app.register_blueprint(scoring_bp, url_prefix='/scoring')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(system_bp, url_prefix='/system')
    app.register_blueprint(flugzeuge_bp, url_prefix='/flugzeuge')
    app.register_blueprint(figures_bp, url_prefix='/figures')
    app.register_blueprint(formular_bp, url_prefix='/formular')
    app.register_blueprint(testdata_bp, url_prefix='/testdata')
    app.register_blueprint(cleanup_bp, url_prefix='/cleanup')