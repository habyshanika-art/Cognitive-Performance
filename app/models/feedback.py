"""
Feedback Model
--------------
Researcher responses to user feedback requests.
Only visible to the requesting user.
"""

from app import db


class Feedback(db.Model):
    """Feedback table - researcher comments for users."""

    __tablename__ = 'feedback'

    id = db.Column(db.Integer, primary_key=True)
    feedback_request_id = db.Column(db.Integer, db.ForeignKey('feedback_request.id'),
                                    nullable=False)
    researcher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, server_default=db.func.now())

    # Relationships
    feedback_request = db.relationship('FeedbackRequest', back_populates='feedback')
    researcher = db.relationship('User', foreign_keys=[researcher_id])
    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<Feedback for request {self.feedback_request_id}>'
