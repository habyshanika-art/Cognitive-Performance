"""
Feedback Request Model
----------------------
User-initiated requests for researcher feedback on cognitive performance.
"""

from app import db


class FeedbackRequest(db.Model):
    """Feedback_request table - user requests for expert review."""

    __tablename__ = 'feedback_request'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    researcher_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(
        db.Enum('pending', 'accepted', 'ignored', 'completed',
                name='feedback_status_enum'),
        default='pending'
    )
    user_message = db.Column(db.Text)
    requested_at = db.Column(db.DateTime, server_default=db.func.now())
    responded_at = db.Column(db.DateTime)

    # Relationships
    user = db.relationship('User', back_populates='feedback_requests',
                          foreign_keys=[user_id])
    researcher = db.relationship('User', foreign_keys=[researcher_id])
    feedback = db.relationship('Feedback', back_populates='feedback_request',
                                uselist=False)

    def __repr__(self):
        return f'<FeedbackRequest {self.id} status={self.status}>'
