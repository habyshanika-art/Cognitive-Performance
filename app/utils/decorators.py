"""
Role-Based Access Control (RBAC) Decorators
--------------------------------------------
Restrict route access based on user role.
Usage: @role_required('admin') or @role_required('researcher', 'admin')
"""

from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user


def role_required(*roles):
    """
    Decorator to require specific role(s) for a route.
    Args:
        *roles: One or more role name strings ('user', 'researcher', 'admin')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to continue.', 'warning')
                return redirect(url_for('auth.login'))

            if current_user.is_blocked:
                flash('Your account has been blocked. Contact administrator.', 'danger')
                return redirect(url_for('auth.logout'))

            if current_user.role_name not in roles:
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Shortcut decorator for admin-only routes."""
    return role_required('admin')(f)


def researcher_required(f):
    """Shortcut decorator for researcher-only routes."""
    return role_required('researcher')(f)


def user_required(f):
    """Shortcut decorator for regular user-only routes."""
    return role_required('user')(f)
