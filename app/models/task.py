"""
Task Model
----------
Represents individual cognitive assessment attempts.
Supports typing, reaction, and memory tasks with validation metadata.
"""

from app import db


class Task(db.Model):
    """Task table - stores each assessment attempt."""

    __tablename__ = 'task'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_type = db.Column(
        db.Enum('typing', 'reaction', 'concentration', 'memory', name='task_type_enum'),
        nullable=False
    )
    attempt_number = db.Column(db.Integer, nullable=False, default=1)
    cycle_number = db.Column(db.Integer, nullable=False, default=1)
    started_at = db.Column(db.DateTime, server_default=db.func.now())
    completed_at = db.Column(db.DateTime)
    completion_time_ms = db.Column(db.Integer)
    score = db.Column(db.Numeric(10, 2))
    status = db.Column(
        db.Enum('in_progress', 'completed', 'abandoned', 'rejected',
                name='task_status_enum'),
        default='in_progress'
    )
    device_type = db.Column(db.String(20))  # desktop | mobile | tablet | unknown
    is_practice = db.Column(db.Boolean, default=False)
    is_valid = db.Column(db.Boolean, default=True)
    validation_flags = db.Column(db.JSON)

    # Relationships
    session = db.relationship('Session', back_populates='tasks')
    user = db.relationship('User', back_populates='tasks')
    interaction_data = db.relationship('InteractionData', back_populates='task',
                                       lazy='dynamic')
    cognitive_metric = db.relationship('CognitiveMetrics', back_populates='task',
                                       uselist=False)

    def __repr__(self):
        return f'<Task {self.task_type} attempt {self.attempt_number}>'
