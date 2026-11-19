"""
Session Model
-------------
Tracks user login and assessment sessions with unique session tokens.
"""

from app import db


class Session(db.Model):
    """Session table - tracks active and historical user sessions."""

    __tablename__ = 'session'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_token = db.Column(db.String(64), unique=True, nullable=False)
    started_at = db.Column(db.DateTime, server_default=db.func.now())
    ended_at = db.Column(db.DateTime)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    user = db.relationship('User', back_populates='sessions')
    tasks = db.relationship('Task', back_populates='session', lazy='dynamic')
    interaction_data = db.relationship('InteractionData', back_populates='session',
                                       lazy='dynamic')

    def __repr__(self):
        return f'<Session {self.session_token[:8]}...>'
