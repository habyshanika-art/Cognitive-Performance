"""
Database Initialization Script
------------------------------
Creates database tables, seeds roles, default accounts, and sample data.

Usage:
    python init_db.py

Default credentials after init:
    Admin:      admin@cognitivemonitor.com / Admin@123
    Researcher: researcher@cognitivemonitor.com / Researcher@123
    User:       user@cognitivemonitor.com / User@123
"""

import os
from datetime import date

import pymysql
from dotenv import load_dotenv

from app import create_app, db
from app.utils.migrations import run_migrations
from app.models.role import Role
from app.models.user import User
from app.models.system_settings import SystemSettings
from app.models.publication import Publication
from app.models.notification import Notification


def ensure_database():
    """Create the MySQL database on XAMPP if it does not exist yet."""
    load_dotenv()
    host = os.getenv('DB_HOST', 'localhost')
    port = int(os.getenv('DB_PORT', '3306'))
    user = os.getenv('DB_USER', 'root')
    password = os.getenv('DB_PASSWORD', '')
    db_name = os.getenv('DB_NAME', 'cognitive_monitoring_db')

    conn = pymysql.connect(
        host=host, port=port, user=user, password=password, charset='utf8mb4',
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
        print(f'Database ready: {db_name}')
    finally:
        conn.close()


def init_database():
    """Initialize database with schema, roles, and default accounts."""
    ensure_database()
    app = create_app('development')

    with app.app_context():
        print('Creating database tables...')
        db.create_all()
        run_migrations()

        roles_data = [
            ('user', 'Regular participant who performs cognitive assessments'),
            ('researcher', 'Research staff who analyze data and publish findings'),
            ('admin', 'System administrator with full access'),
        ]
        for name, desc in roles_data:
            if not Role.query.filter_by(name=name).first():
                db.session.add(Role(name=name, description=desc))
        db.session.commit()
        print('Roles seeded.')

        admin_role = Role.query.filter_by(name='admin').first()
        admin = User.query.filter_by(email='admin@cognitivemonitor.com').first()
        if not admin:
            admin = User(
                role_id=admin_role.id,
                username='admin',
                email='admin@cognitivemonitor.com',
                first_name='System',
                last_name='Administrator',
                email_verified=True,
            )
            admin.set_password('Admin@123')
            db.session.add(admin)
            print('Admin account created: admin@cognitivemonitor.com / Admin@123')
        else:
            if not admin.username:
                admin.username = 'admin'
            admin.email_verified = True
            db.session.commit()

        researcher_role = Role.query.filter_by(name='researcher').first()
        researcher = User.query.filter_by(email='researcher@cognitivemonitor.com').first()
        if not researcher:
            researcher = User(
                role_id=researcher_role.id,
                username='researcher',
                email='researcher@cognitivemonitor.com',
                first_name='Default',
                last_name='Researcher',
                email_verified=True,
            )
            researcher.set_password('Researcher@123')
            db.session.add(researcher)
            print('Researcher: researcher@cognitivemonitor.com / Researcher@123')
        else:
            if not researcher.username:
                researcher.username = 'researcher'
            researcher.email_verified = True
            db.session.commit()

        user_role = Role.query.filter_by(name='user').first()
        sample_user = User.query.filter_by(email='user@cognitivemonitor.com').first()
        if not sample_user:
            sample_user = User(
                role_id=user_role.id,
                username='user',
                email='user@cognitivemonitor.com',
                first_name='Sample',
                last_name='Participant',
                consent_given=True,
                email_verified=True,
            )
            sample_user.set_password('User@123')
            sample_user.ensure_anonymised_id()
            db.session.add(sample_user)
            print('User: user@cognitivemonitor.com / User@123')
        else:
            if not sample_user.username:
                sample_user.username = 'user'
            sample_user.email_verified = True
            db.session.commit()

        db.session.commit()

        researcher = User.query.filter_by(username='researcher').first()
        if researcher and Publication.query.count() == 0:
            sample_pubs = [
                Publication(
                    author_id=researcher.id,
                    title='Temporal Interaction Data for Early Cognitive Change Detection',
                    description='This study explores how typing speed and reaction time patterns '
                                'can indicate subtle cognitive changes in young adults over time.',
                    content='Full article content placeholder for interim demonstration.',
                    date_published=date(2025, 11, 15),
                    status='published'
                ),
                Publication(
                    author_id=researcher.id,
                    title='Digital Assessments as Continuous Cognitive Monitoring Tools',
                    description='An overview of web-based cognitive assessments and their role '
                                'in longitudinal performance tracking for research participants.',
                    content='Full article content placeholder for interim demonstration.',
                    date_published=date(2026, 1, 20),
                    status='published'
                ),
                Publication(
                    author_id=researcher.id,
                    title='Reaction Time Variability in Healthy Young Adults',
                    description='Analysis of reaction time consistency across multiple attempts '
                                'and its correlation with overall cognitive performance scores.',
                    content='Full article content placeholder for interim demonstration.',
                    date_published=date(2026, 3, 10),
                    status='published'
                ),
            ]
            for pub in sample_pubs:
                db.session.add(pub)
            db.session.commit()
            print('Sample publications seeded.')

        settings = [
            ('site_name', 'Cognitive Performance Monitoring System',
             'Application display name'),
            ('assessments_per_cycle', '5', 'Attempts required per assessment'),
            ('maintenance_mode', '0', '1 = maintenance enabled'),
            ('contact_email', 'haby@gmail.com', 'Public contact email'),
        ]
        for key, value, desc in settings:
            if not SystemSettings.query.filter_by(setting_key=key).first():
                db.session.add(SystemSettings(
                    setting_key=key, setting_value=value, description=desc
                ))

        db.session.commit()
        print('Database initialization complete!')


if __name__ == '__main__':
    init_database()
