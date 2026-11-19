"""
User Model
----------
Central user entity for all actors (User, Researcher, Admin).
Integrates with Flask-Login for session management.
"""

import secrets

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db


def generate_anonymised_id():
    """Public research ID, e.g. P-A1B2C3 — never exposes personal name."""
    return f'P-{secrets.token_hex(3).upper()}'


class User(UserMixin, db.Model):
    """User table - stores all system actors with role-based access."""

    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    profile_picture = db.Column(db.String(255))
    is_blocked = db.Column(db.Boolean, default=False)
    anonymised_id = db.Column(db.String(20), unique=True)
    consent_given = db.Column(db.Boolean, default=False)
    consent_given_at = db.Column(db.DateTime)
    consent_version = db.Column(db.String(20))
    data_withdrawn = db.Column(db.Boolean, default=False)
    notify_assessment_reminders = db.Column(db.Boolean, default=True)
    notify_performance_alerts = db.Column(db.Boolean, default=True)
    notify_publications = db.Column(db.Boolean, default=True)
    notify_email = db.Column(db.Boolean, default=True)
    # Email verification (Brevo OTP)
    email_verified = db.Column(db.Boolean, default=False)
    email_verified_at = db.Column(db.DateTime)
    email_otp_hash = db.Column(db.String(255))
    email_otp_expires_at = db.Column(db.DateTime)
    email_otp_attempts = db.Column(db.Integer, default=0)
    email_otp_sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(),
                          onupdate=db.func.now())

    # Relationships
    role = db.relationship('Role', back_populates='users')
    sessions = db.relationship('Session', back_populates='user', lazy='dynamic')
    tasks = db.relationship('Task', back_populates='user', lazy='dynamic')
    cognitive_metrics = db.relationship('CognitiveMetrics', back_populates='user',
                                        lazy='dynamic')
    aggregated_metrics = db.relationship('AggregatedMetrics', back_populates='user',
                                         lazy='dynamic')
    alerts = db.relationship('Alert', back_populates='user', lazy='dynamic')
    publications = db.relationship('Publication', back_populates='author',
                                   lazy='dynamic')
    feedback_requests = db.relationship(
        'FeedbackRequest', back_populates='user',
        foreign_keys='FeedbackRequest.user_id', lazy='dynamic'
    )
    notifications = db.relationship('Notification', back_populates='user',
                                    lazy='dynamic')
    email_messages = db.relationship('EmailMessage', back_populates='user',
                                     lazy='dynamic')

    def set_password(self, password):
        """Hash and store password securely."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password against stored hash."""
        return check_password_hash(self.password_hash, password)

    def ensure_anonymised_id(self):
        """Assign anonymised research ID if missing."""
        if not self.anonymised_id:
            # Retry on rare collision
            for _ in range(5):
                candidate = generate_anonymised_id()
                exists = User.query.filter_by(anonymised_id=candidate).first()
                if not exists:
                    self.anonymised_id = candidate
                    break

    @property
    def full_name(self):
        """Return user's full display name."""
        return f'{self.first_name} {self.last_name}'

    @property
    def display_id(self):
        """Researcher-facing anonymised participant ID."""
        return self.anonymised_id or f'P-{self.id:06d}'

    @property
    def role_name(self):
        """Return role name string for RBAC checks."""
        return self.role.name if self.role else None

    def is_admin(self):
        return self.role_name == 'admin'

    def is_researcher(self):
        return self.role_name == 'researcher'

    def is_regular_user(self):
        return self.role_name == 'user'

    def profile_picture_url(self):
        """Return profile picture path or default avatar."""
        if self.profile_picture:
            return f'/static/uploads/profiles/{self.profile_picture}'
        return None

    def unread_email_count(self):
        return self.email_messages.filter_by(is_read=False).count()

    def __repr__(self):
        return f'<User {self.username}>'
