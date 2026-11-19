"""
Cognitive Metrics Model
-----------------------
Per-attempt calculated metrics after each assessment completion.
"""

from app import db


class CognitiveMetrics(db.Model):
    """Cognitive_metrics table - calculated scores per attempt."""

    __tablename__ = 'cognitive_metrics'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    task_type = db.Column(
        db.Enum('typing', 'reaction', 'concentration', 'memory',
                name='cognitive_task_type_enum'),
        nullable=False
    )
    attempt_number = db.Column(db.Integer, nullable=False)
    cycle_number = db.Column(db.Integer, nullable=False, default=1)
    typing_speed_wpm = db.Column(db.Numeric(10, 2))
    response_time_ms = db.Column(db.Integer)
    concentration_score = db.Column(db.Numeric(10, 2))
    memory_score = db.Column(db.Numeric(10, 2))
    error_rate = db.Column(db.Numeric(5, 2))
    calculated_at = db.Column(db.DateTime, server_default=db.func.now())

    # Relationships
    user = db.relationship('User', back_populates='cognitive_metrics')
    task = db.relationship('Task', back_populates='cognitive_metric')

    def __repr__(self):
        return f'<CognitiveMetrics {self.task_type} #{self.attempt_number}>'
