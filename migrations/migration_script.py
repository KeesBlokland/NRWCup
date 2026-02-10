# migration_script.py
import os
import sys
from app_main import app
from flask_migrate import Migrate
from app.models import db

migrate = Migrate(app, db)