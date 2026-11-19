"""
Aggregated Metrics Model
------------------------
Stores averaged cognitive scores after completing a full assessment cycle,
plus baseline/deviation fields used for persistent-change alerts.
"""

from app import db


class AggregatedMetrics(db.Model):
    """Aggregated_metrics table - averages after each assessment cycle."""

    __tablename__ = 'aggregated_metrics'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    avg_typing_speed = db.Column(db.Numeric(10, 2))
    avg_response_time = db.Column(db.Numeric(10, 2))
    avg_concentration_score = db.Column(db.Numeric(10, 2))
    avg_memory_score = db.Column(db.Numeric(10, 2))
    overall_cognitive_score = db.Column(db.Numeric(10, 2))
    cycle_number = db.Column(db.Integer, default=1)
    # Deviation vs personal baseline (negative typing/memory/overall = worse;
    # positive reaction = slower/worse). Absolute z-like percent scores.
    typing_deviation = db.Column(db.Numeric(10, 2))
    reaction_deviation = db.Column(db.Numeric(10, 2))
    memory_deviation = db.Column(db.Numeric(10, 2))
    concentration_deviation = db.Column(db.Numeric(10, 2))
    overall_deviation = db.Column(db.Numeric(10, 2))
    is_baseline_cycle = db.Column(db.Boolean, default=False)
    is_flagged = db.Column(db.Boolean, default=False)
    calculated_at = db.Column(db.DateTime, server_default=db.func.now())

    # Relationships
    user = db.relationship('User', back_populates='aggregated_metrics')

    def __repr__(self):
        return f'<AggregatedMetrics user={self.user_id} cycle={self.cycle_number}>'
