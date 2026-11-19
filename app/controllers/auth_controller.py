"""
Authentication Controller
-------------------------
Shared login, register, logout, email verification, and forgot-password.
"""

import re
from datetime import datetime

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, session
)
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_

from app import db
from app.models.user import User
from app.models.role import Role
from app.models.session import Session
from app.utils.helpers import (
    generate_session_token, log_action, get_dashboard_redirect,
    split_full_name, save_profile_picture
)
from app.utils.email_verification import (
    issue_email_verification_otp, verify_email_otp, seconds_until_resend,
)

auth_bp = Blueprint('auth', __name__)

EMAIL_PATTERN = re.compile(r'^[^@]+@[^@]+\.[^@]+$')


def find_user_by_login(login_value):
    """Find user by email or username (case-insensitive)."""
    login_value = login_value.strip().lower()
    if EMAIL_PATTERN.match(login_value):
        return User.query.filter_by(email=login_value).first()
    return User.query.filter(
        or_(User.username == login_value, User.email == login_value)
    ).first()


def _require_email_verified(user):
    """Block login until email OTP verification succeeds."""
    if getattr(user, 'email_verified', True):
        return True
    session['pending_verify_email'] = user.email
    flash('Please verify your email before logging in.', 'warning')
    return False


@auth_bp.route('/login', methods=['GET', 'POST'])
@auth_bp.route('/auth/login', methods=['GET', 'POST'])
def login():
    """Single shared login page for User, Researcher, and Admin."""
    if current_user.is_authenticated:
        from app.utils.helpers import is_maintenance_mode
        if is_maintenance_mode() and not current_user.is_admin():
            logout_user()
        else:
            return redirect(get_dashboard_redirect())

    if request.method == 'POST':
        login_value = request.form.get('login', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember_me') == 'on'

        if not login_value or not password:
            flash('Email/username and password are required.', 'danger')
            return render_template('auth/login.html')

        user = find_user_by_login(login_value)

        if user is None or not user.check_password(password):
            flash('Invalid email/username or password.', 'danger')
            return render_template('auth/login.html')

        if user.is_blocked:
            flash('Your account has been blocked. Contact the administrator.', 'danger')
            return render_template('auth/login.html')

        if not _require_email_verified(user):
            return redirect(url_for('auth.verify_email', email=user.email))

        from app.utils.helpers import is_maintenance_mode
        if is_maintenance_mode() and not user.is_admin():
            flash('The system is under maintenance. Please try again later.', 'warning')
            return render_template('auth/login.html')

        session_record = Session(
            user_id=user.id,
            session_token=generate_session_token(),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:255]
        )
        db.session.add(session_record)
        db.session.commit()

        login_user(user, remember=remember)
        log_action('login', f'User {user.email} logged in', user.id)
        flash(f'Welcome back, {user.first_name}!', 'success')
        return redirect(get_dashboard_redirect())

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
@auth_bp.route('/auth/register', methods=['GET', 'POST'])
def register():
    """User registration — creates account, then requires email OTP verification."""
    if current_user.is_authenticated:
        return redirect(get_dashboard_redirect())

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        date_of_birth = request.form.get('date_of_birth') or None
        gender = request.form.get('gender') or None

        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if not username:
            errors.append('Username is required.')
        elif not re.match(r'^[a-zA-Z0-9_]{3,30}$', username):
            errors.append('Username must be 3–30 characters (letters, numbers, underscore).')
        if not email:
            errors.append('Email is required.')
        elif not EMAIL_PATTERN.match(email):
            errors.append('Enter a valid email address.')
        if not password:
            errors.append('Password is required.')
        elif len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')

        if errors:
            for msg in errors:
                flash(msg, 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('Email is already registered.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash('Username is already taken.', 'danger')
            return render_template('auth/register.html')

        user_role = Role.query.filter_by(name='user').first()
        if not user_role:
            flash('System error: default role not found. Run database setup.', 'danger')
            return render_template('auth/register.html')

        first_name, last_name = split_full_name(full_name)
        profile_file = save_profile_picture(request.files.get('profile_picture'))

        user = User(
            role_id=user_role.id,
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            gender=gender,
            profile_picture=profile_file,
            notify_email=True,
            consent_given=False,
            email_verified=False,
        )
        user.set_password(password)
        user.ensure_anonymised_id()
        db.session.add(user)
        db.session.commit()

        ok, message, debug_otp = issue_email_verification_otp(user, force=True)
        session['pending_verify_email'] = user.email
        log_action('register', f'New user registered (pending email verify): {email}', user.id)

        if ok:
            flash('Account created. Enter the 6-digit code sent to your email.', 'success')
            if debug_otp:
                flash(f'DEBUG OTP (Brevo not configured): {debug_otp}', 'info')
        else:
            flash(
                f'Account created, but the verification email could not be sent: {message}',
                'warning',
            )

        return redirect(url_for('auth.verify_email', email=user.email))

    return render_template('auth/register.html')


@auth_bp.route('/verify-email', methods=['GET', 'POST'])
@auth_bp.route('/auth/verify-email', methods=['GET', 'POST'])
def verify_email():
    """OTP verification page after registration (or blocked login)."""
    if current_user.is_authenticated and getattr(current_user, 'email_verified', False):
        return redirect(get_dashboard_redirect())

    email = (
        request.values.get('email', '').strip().lower()
        or session.get('pending_verify_email', '')
    )
    user = User.query.filter_by(email=email).first() if email else None

    if request.method == 'POST':
        action = request.form.get('action', 'verify')
        email = request.form.get('email', email).strip().lower()
        user = User.query.filter_by(email=email).first() if email else None

        if not user:
            flash('Account not found for that email.', 'danger')
            return render_template(
                'auth/verify_email.html',
                email=email,
                resend_wait=0,
            )

        if action == 'resend':
            ok, message, debug_otp = issue_email_verification_otp(user)
            flash(message, 'success' if ok else 'danger')
            if debug_otp:
                flash(f'DEBUG OTP (Brevo not configured): {debug_otp}', 'info')
            session['pending_verify_email'] = user.email
            return redirect(url_for('auth.verify_email', email=user.email))

        code = request.form.get('otp', '').strip()
        ok, message = verify_email_otp(user, code)
        if ok:
            session.pop('pending_verify_email', None)
            log_action('email_verified', f'Email verified for {user.email}', user.id)
            flash(message, 'success')
            return redirect(url_for('auth.login'))

        flash(message, 'danger')
        return render_template(
            'auth/verify_email.html',
            email=user.email,
            resend_wait=seconds_until_resend(user),
        )

    resend_wait = seconds_until_resend(user) if user else 0
    return render_template(
        'auth/verify_email.html',
        email=email,
        resend_wait=resend_wait,
    )


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password — interim: notify admin contact."""
    if current_user.is_authenticated:
        return redirect(get_dashboard_redirect())

    if request.method == 'POST':
        login_value = request.form.get('login', '').strip()
        if not login_value:
            flash('Please enter your email or username.', 'danger')
            return render_template('auth/forgot_password.html')

        user = find_user_by_login(login_value)
        if user:
            try:
                from app.utils.email_service import generate_password_reset_code
                generate_password_reset_code(user)
                log_action('password_reset_request',
                           f'Password reset code generated for {user.email}', user.id)
            except Exception:
                log_action('password_reset_request',
                           f'Password reset code failed for {user.email}', user.id)
        flash(
            'If an account exists, a reset code was sent to that email '
            '(and stored in the Profile → Email inbox after login).',
            'info',
        )
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Log out current user and end active session records."""
    user_id = current_user.id
    email = current_user.email

    active_sessions = Session.query.filter_by(
        user_id=user_id, is_active=True
    ).all()
    for sess in active_sessions:
        sess.is_active = False
        sess.ended_at = datetime.utcnow()
    db.session.commit()

    log_action('logout', f'User {email} logged out', user_id)
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
