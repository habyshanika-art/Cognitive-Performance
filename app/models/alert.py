"""
Alert Model
-----------
System alerts for researchers when user performance changes are detected.
"""

from app import db


class Alert(db.Model):
    """Alert table - notifications for performance monitoring."""

    __tablename__ = 'alert'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    alert_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    severity = db.Column(
        db.Enum('low', 'medium', 'high', name='alert_severity_enum'),
        default='medium'
    )
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # Relationships
    user = db.relationship('User', back_populates='alerts')

    def __repr__(self):
        return f'<Alert {self.alert_type} for user {self.user_id}>'
