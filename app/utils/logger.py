# app/utils/logger.py
import logging
import sys
import os
from datetime import datetime

class DBLogger:
    _instance = None
    
    @classmethod
    def get_logger(cls):
        if cls._instance is None:
            cls._instance = cls._setup_logger()
        
        # Check if we're in a Flask app context
        try:
            from flask import current_app
            if current_app:
                # Check if logging is enabled in database
                from app.models import SystemConfig, db
                try:
                    config = SystemConfig.query.filter_by(config_key='logging_enabled').first()
                    enabled = config and config.config_value == 'true'
                    
                    # Set logger level based on config
                    if enabled:
                        cls._instance.setLevel(logging.INFO)
                    else:
                        cls._instance.setLevel(logging.ERROR)  # Only critical logs
                except Exception:
                    # If any error, keep default level
                    pass
        except Exception:
            # Not in Flask context or other error
            pass
            
        return cls._instance
    
    @staticmethod
    def _setup_logger():
        logger = logging.getLogger('nrwcup_db')
        logger.setLevel(logging.INFO)
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.getcwd(), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # Create handlers
        # File handler with daily rotation
        log_file = os.path.join(log_dir, f'db_{datetime.now().strftime("%Y-%m-%d")}.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Console handler for debugging
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        
        # Create formatter and add it to handlers
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
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