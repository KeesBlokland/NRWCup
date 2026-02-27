# app/utils/logger.py
import logging
import sys
import os
from datetime import datetime

# Project root: this file lives at app/utils/logger.py → two levels up
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DBLogger:
    _instance = None
    _file_handler_installed = False
    _level_checked = False

    @classmethod
    def get_logger(cls):
        if cls._instance is None:
            cls._instance = cls._setup_logger()

        # Read logging_enabled from DB once per process startup only
        if not cls._level_checked:
            try:
                from flask import current_app
                if current_app:
                    from app.models import SystemConfig
                    try:
                        config = SystemConfig.query.filter_by(config_key='logging_enabled').first()
                        enabled = config and config.config_value == 'true'
                        cls._instance.setLevel(logging.INFO if enabled else logging.ERROR)
                        cls._level_checked = True
                    except Exception:
                        pass
            except Exception:
                pass

        return cls._instance

    @staticmethod
    def _setup_logger():
        # Create the nrwcup_db logger (used by DBLogger.info/error/etc.)
        logger = logging.getLogger('nrwcup_db')
        logger.setLevel(logging.INFO)

        # Create logs directory
        log_dir = os.path.join(PROJECT_ROOT, 'logs')
        os.makedirs(log_dir, exist_ok=True)

        # File handler with daily rotation
        log_file = os.path.join(log_dir, f'db_{datetime.now().strftime("%Y-%m-%d")}.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        # Also attach the file handler to the 'app' logger so all blueprint
        # loggers (app.routes.bp_system, app.routes.bp_scoring, etc.) write
        # to the same log file automatically.
        if not DBLogger._file_handler_installed:
            app_logger = logging.getLogger('app')
            app_logger.setLevel(logging.INFO)
            app_logger.addHandler(file_handler)
            DBLogger._file_handler_installed = True

        return logger

    @classmethod
    def info(cls, message):
        cls.get_logger().info(message)

    @classmethod
    def error(cls, message, exc_info=False):
        cls.get_logger().error(message, exc_info=exc_info)

    @classmethod
    def warning(cls, message):
        cls.get_logger().warning(message)

    @classmethod
    def debug(cls, message):
        cls.get_logger().debug(message)
