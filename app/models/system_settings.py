"""
System Settings Model
---------------------
Key-value configuration store managed by admin.
"""

from app import db


class SystemSettings(db.Model):
    """System_settings table - admin-managed configuration."""

    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text)
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, server_default=db.func.now(),
                          onupdate=db.func.now())

    def __repr__(self):
        return f'<SystemSettings {self.setting_key}>'
