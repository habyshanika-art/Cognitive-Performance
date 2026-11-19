"""
Interaction Data Model
----------------------
Stores raw temporal interaction data collected during assessments:
typing speed, response time, completion time, error rate, timestamps.
"""

from app import db


class InteractionData(db.Model):
    """Interaction_data table - raw metrics from user interactions."""

    __tablename__ = 'interaction_data'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
    typing_speed_wpm = db.Column(db.Numeric(10, 2))
    response_time_ms = db.Column(db.Integer)
    task_completion_time_ms = db.Column(db.Integer)
    error_rate = db.Column(db.Numeric(5, 2))
    event_type = db.Column(db.String(50))
    event_data = db.Column(db.JSON)
    recorded_at = db.Column(db.DateTime, server_default=db.func.now())

    # Relationships
    task = db.relationship('Task', back_populates='interaction_data')
    user = db.relationship('User')
    session = db.relationship('Session', back_populates='interaction_data')

    def __repr__(self):
        return f'<InteractionData task={self.task_id}>'
