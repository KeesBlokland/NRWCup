"""
File: app/config.py
Version: 1.1.0
Created: 2024-12-05
Last Modified: 2026-02-10
Description: Configuration settings for Flask application - credentials via environment variables
"""

import os

class Config:
    # Get the app folder path
    basedir = os.path.abspath(os.path.dirname(__file__))
    # Go up one level to the project root
    rootdir = os.path.dirname(basedir)
    # Create database path in project root's instance folder
    db_path = os.path.join(rootdir, 'instance', 'NRWCup2025.db')

    # Database settings
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + db_path
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # Application settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-this'
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    # Scoring settings (can be overridden via SystemConfig in the database)
    DROP_WORST_ROUND_THRESHOLD = 3  # Drop lowest round when total rounds >= this number

    # Admin configuration
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'NRWAdmin')

    # Email configuration - all from environment variables
    MAIL_SERVER = os.environ.get('MAIL_SERVER', '')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 465))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_ENABLED = os.environ.get('MAIL_ENABLED', 'false').lower() == 'true'
