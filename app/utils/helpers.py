"""
Helper Utilities
----------------
Common functions: logging, session tokens, role-based redirects,
file uploads, and name parsing.
"""

import os
import secrets
import uuid
from flask import request, current_app
from flask_login import current_user
from werkzeug.utils import secure_filename

from app import db
from app.models.system_log import SystemLog


def generate_session_token():
    """Generate a unique 32-byte hex session token."""
    return secrets.token_hex(32)


def split_full_name(full_name):
    """Split a full name string into first and last name parts."""
    parts = full_name.strip().split(None, 1)
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], parts[1]


def allowed_file(filename):
    """Check if uploaded file has an allowed image extension."""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in current_app.config.get('ALLOWED_EXTENSIONS', set())


def save_profile_picture(file_storage):
    """
    Save uploaded profile picture to static/uploads/profiles.
    Returns stored filename or None if invalid.
    """
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None

    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)

    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(upload_dir, filename))
    return filename


def delete_profile_picture(filename):
    """Remove a stored profile picture file if it exists."""
    if not filename:
        return
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    if os.path.isfile(path):
        os.remove(path)


def log_action(action, details=None, user_id=None):
    """
    Record an action in the system_log table.
    Args:
        action: Short action name (e.g. 'login', 'assessment_complete')
        details: Optional description text
        user_id: Optional user ID (defaults to current_user)
    """
    uid = user_id
    if uid is None and current_user.is_authenticated:
        uid = current_user.id

    log_entry = SystemLog(
        user_id=uid,
        action=action,
        details=details,
        ip_address=request.remote_addr if request else None
    )
    db.session.add(log_entry)
    db.session.commit()


def get_system_setting(key, default=None):
    """Read a value from system_settings by key."""
    from app.models.system_settings import SystemSettings
    row = SystemSettings.query.filter_by(setting_key=key).first()
    return row.setting_value if row else default


def set_system_setting(key, value):
    """Create or update a system_settings row."""
    from app.models.system_settings import SystemSettings
    row = SystemSettings.query.filter_by(setting_key=key).first()
    if row:
        row.setting_value = value
    else:
        row = SystemSettings(setting_key=key, setting_value=value)
        db.session.add(row)
    db.session.commit()
    return row


def is_maintenance_mode():
    """Return True when maintenance mode is enabled."""
    return get_system_setting('maintenance_mode', '0') == '1'


def notify_users_publication(publication):
    """Notify users who opted in when a publication is published."""
    from app.models.role import Role
    from app.models.user import User
    from app.models.notification import Notification

    users = User.query.join(Role).filter(
        Role.name == 'user',
        User.notify_publications.is_(True),
        User.data_withdrawn.is_(False),
    ).all()
    for user in users:
        notif = Notification(
            user_id=user.id,
            notification_type='publication',
            title='New Research Publication',
            message=f'"{publication.title}" has been published.',
            link_url=f'/publications/{publication.id}',
        )
        db.session.add(notif)
    if users:
        db.session.commit()
        try:
            from app.utils.email_service import send_user_email
            for user in users:
                send_user_email(
                    user,
                    'New research publication — CogMonitor',
                    (
                        f'Hello {user.first_name},\n\n'
                        f'A new publication is available: "{publication.title}".\n'
                        f'Open CogMonitor → Publications to read it.\n'
                    ),
                    category='notification',
                    also_notify=False,
                    link_url=f'/publications/{publication.id}',
                )
        except Exception:
            pass


def get_dashboard_redirect():
    """
    Return the correct dashboard URL based on logged-in user's role.
    Used after login for automatic role-based redirection.
    """
    from flask import url_for

    if not current_user.is_authenticated:
        return url_for('auth.login')

    role = current_user.role_name
    if role == 'admin':
        return url_for('admin.dashboard')
    elif role == 'researcher':
        return url_for('researcher.dashboard')
    else:
        return url_for('user.dashboard')
