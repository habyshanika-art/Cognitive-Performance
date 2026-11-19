"""
Email Message Model
-------------------
In-app email inbox for notifications, password codes, and system alerts.
Messages are always stored here; SMTP delivery is attempted when configured.
"""

from app import db


class EmailMessage(db.Model):
    """email_message table — user-facing email inbox."""

    __tablename__ = 'email_message'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    category = db.Column(
        db.String(50), nullable=False, default='notification'
    )  # notification | password_code | alert | system | consent
    code = db.Column(db.String(32))  # one-time codes (password reset, etc.)
    is_read = db.Column(db.Boolean, default=False)
    sent_via = db.Column(db.String(20), default='inbox')  # inbox | smtp | both
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship('User', back_populates='email_messages')

    def __repr__(self):
        return f'<EmailMessage {self.id} to={self.user_id}>'
