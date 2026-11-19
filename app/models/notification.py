"""
Notification Model
------------------
Stores user-facing notifications for feedback, publications,
and assessment reminders.
"""

from app import db


class Notification(db.Model):
    """Notification table - alerts shown on the user dashboard."""

    __tablename__ = 'notification'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    notification_type = db.Column(
        db.Enum(
            'feedback', 'publication', 'assessment_reminder', 'system',
            'performance_alert', 'cycle_complete', 'consent', 'password_code',
            name='notification_type_enum',
        ),
        nullable=False
    )
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link_url = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # Relationships
    user = db.relationship('User', back_populates='notifications')

    def __repr__(self):
        return f'<Notification {self.title[:30]}>'
