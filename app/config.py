"""
Application Configuration Module
---------------------------------
Loads environment variables and provides Flask configuration classes.
Supports development (XAMPP MySQL) and production environments.
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

# Load variables from .env file in project root
load_dotenv()


class Config:
    """Base configuration shared across all environments."""

    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}

    # Assessment settings
    ASSESSMENTS_PER_CYCLE = 5
    BASELINE_CYCLES = 3
    PERSISTENCE_CYCLES = 2
    CONSENT_VERSION = '1.0'
    INTERIM_TASK_TYPES = ['typing', 'reaction', 'memory', 'concentration']
    TASK_TYPES = ['typing', 'reaction', 'concentration', 'memory']

    # File uploads
    UPLOAD_FOLDER = 'uploads/profiles'
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # Session / Remember Me
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # Email (optional SMTP — inbox always works without these)
    MAIL_SERVER = os.getenv('MAIL_SERVER', '')
    MAIL_PORT = int(os.getenv('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.getenv(
        'MAIL_DEFAULT_SENDER',
        os.getenv('BREVO_SENDER_EMAIL', 'noreply@cognitivemonitor.local'),
    )

    # Brevo transactional email (API key NEVER goes in frontend JS)
    BREVO_API_KEY = os.getenv('BREVO_API_KEY', '')
    BREVO_SENDER_EMAIL = os.getenv('BREVO_SENDER_EMAIL', '')
    BREVO_SENDER_NAME = os.getenv('BREVO_SENDER_NAME', 'CogMonitor')

    # Role names (must match database role table)
    ROLE_USER = 'user'
    ROLE_RESEARCHER = 'researcher'
    ROLE_ADMIN = 'admin'


class DevelopmentConfig(Config):
    """Development configuration for local XAMPP MySQL."""

    DEBUG = True
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_NAME = os.getenv('DB_NAME', 'cognitive_monitoring_db')

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        f"?charset=utf8mb4"
    )

    # Absolute path for uploaded profile pictures
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads', 'profiles')


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')


# Map environment name to config class
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
