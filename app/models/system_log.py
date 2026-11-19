"""
System Log Model
----------------
Audit trail for admin monitoring of system actions.
"""

from app import db


class SystemLog(db.Model):
    """System_log table - records user and system actions."""

    __tablename__ = 'system_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # Relationships
    user = db.relationship('User')

    def __repr__(self):
        return f'<SystemLog {self.action}>'
