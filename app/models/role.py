"""
Role Model
----------
Represents system roles: user, researcher, admin.
Used for Role-Based Access Control (RBAC).
"""

from app import db


class Role(db.Model):
    """Role table - defines access levels in the system."""

    __tablename__ = 'role'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # Relationship: one role has many users
    users = db.relationship('User', back_populates='role', lazy='dynamic')

    def __repr__(self):
        return f'<Role {self.name}>'
