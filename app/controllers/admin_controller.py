"""
Admin Dashboard Controller
--------------------------
Full admin module: user management, publications, feedback,
alerts, audit logs, system settings, metrics, and notifications.
"""

import csv
import io
import re
from datetime import datetime, date

from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, Response, current_app
)
from flask_login import login_required, current_user
from sqlalchemy import desc, func, or_

from app import db
from app.models.user import User
from app.models.role import Role
from app.models.session import Session
from app.models.task import Task
from app.models.cognitive_metrics import CognitiveMetrics
from app.models.publication import Publication
from app.models.feedback_request import FeedbackRequest
from app.models.alert import Alert
from app.models.system_log import SystemLog
from app.models.system_settings import SystemSettings
from app.models.notification import Notification
from app.utils.decorators import admin_required
from app.utils.helpers import log_action, split_full_name, get_system_setting, set_system_setting
from app.utils.metrics import get_user_averages, get_attempt_count

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

EMAIL_PATTERN = re.compile(r'^[^@]+@[^@]+\.[^@]+$')
PER_PAGE = 15


def _paginate(query):
    """Simple offset pagination from ?page= query param."""
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    total = query.count()
    items = query.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    return items, page, total, total_pages


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin overview with KPIs and recent activity."""
    total_users = User.query.join(Role).filter(Role.name == 'user').count()
    total_researchers = User.query.join(Role).filter(Role.name == 'researcher').count()
    blocked_users = User.query.filter_by(is_blocked=True).count()
    active_sessions = Session.query.filter_by(is_active=True).count()
    total_assessments = Task.query.filter_by(status='completed').count()
    pending_feedback = FeedbackRequest.query.filter_by(status='pending').count()
    unread_alerts = Alert.query.filter_by(is_read=False).count()
    total_publications = Publication.query.count()

    recent_logs = SystemLog.query.order_by(desc(SystemLog.created_at)).limit(10).all()
    recent_users = User.query.order_by(desc(User.created_at)).limit(5).all()

    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        total_researchers=total_researchers,
        blocked_users=blocked_users,
        active_sessions=active_sessions,
        total_assessments=total_assessments,
        pending_feedback=pending_feedback,
        unread_alerts=unread_alerts,
        total_publications=total_publications,
        recent_logs=recent_logs,
        recent_users=recent_users,
        maintenance_mode=get_system_setting('maintenance_mode', '0') == '1',
    )


# ─── User Management ─────────────────────────────────────────────────────────

@admin_bp.route('/users')
@login_required
@admin_required
def users_list():
    """List all users with search and role filter."""
    search = request.args.get('q', '').strip()
    role_filter = request.args.get('role', '')
    status_filter = request.args.get('status', '')

    query = User.query.join(Role).order_by(desc(User.created_at))

    if search:
        like = f'%{search}%'
        query = query.filter(or_(
            User.username.ilike(like),
            User.email.ilike(like),
            User.first_name.ilike(like),
            User.last_name.ilike(like),
        ))
    if role_filter:
        query = query.filter(Role.name == role_filter)
    if status_filter == 'blocked':
        query = query.filter(User.is_blocked.is_(True))
    elif status_filter == 'active':
        query = query.filter(User.is_blocked.is_(False))

    users, page, total, total_pages = _paginate(query)
    roles = Role.query.order_by(Role.name).all()

    return render_template(
        'admin/users/list.html',
        users=users, roles=roles, page=page, total=total,
        total_pages=total_pages, search=search,
        role_filter=role_filter, status_filter=status_filter,
    )


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def users_create():
    """Create a new user, researcher, or admin account."""
    roles = Role.query.order_by(Role.name).all()

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role_id = request.form.get('role_id', type=int)

        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if not username or not re.match(r'^[a-zA-Z0-9_]{3,30}$', username):
            errors.append('Username must be 3–30 characters (letters, numbers, underscore).')
        if not email or not EMAIL_PATTERN.match(email):
            errors.append('A valid email is required.')
        if not password or len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if not role_id:
            errors.append('Role is required.')

        if errors:
            for msg in errors:
                flash(msg, 'danger')
            return render_template('admin/users/form.html', roles=roles, user=None)

        if User.query.filter_by(email=email).first():
            flash('Email is already registered.', 'danger')
            return render_template('admin/users/form.html', roles=roles, user=None)
        if User.query.filter_by(username=username).first():
            flash('Username is already taken.', 'danger')
            return render_template('admin/users/form.html', roles=roles, user=None)

        first_name, last_name = split_full_name(full_name)
        user = User(
            role_id=role_id,
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            email_verified=True,
            email_verified_at=datetime.utcnow(),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        log_action('admin_user_create', f'Created user {email} (role_id={role_id})')
        flash(f'Account created for {email}.', 'success')
        return redirect(url_for('admin.users_list'))

    return render_template('admin/users/form.html', roles=roles, user=None)


@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def users_view(user_id):
    """View user details, sessions, and assessment summary."""
    user = User.query.get_or_404(user_id)
    averages = get_user_averages(user.id)
    typing_attempts = get_attempt_count(user.id, 'typing')
    reaction_attempts = get_attempt_count(user.id, 'reaction')
    recent_tasks = Task.query.filter_by(user_id=user.id).order_by(
        desc(Task.completed_at)
    ).limit(10).all()
    feedback_requests = FeedbackRequest.query.filter_by(
        user_id=user.id
    ).order_by(desc(FeedbackRequest.requested_at)).limit(5).all()
    sessions = Session.query.filter_by(user_id=user.id).order_by(
        desc(Session.started_at)
    ).limit(5).all()

    return render_template(
        'admin/users/view.html',
        user=user,
        averages=averages,
        typing_attempts=typing_attempts,
        reaction_attempts=reaction_attempts,
        recent_tasks=recent_tasks,
        feedback_requests=feedback_requests,
        sessions=sessions,
    )


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def users_edit(user_id):
    """Edit user profile, role, or reset password."""
    user = User.query.get_or_404(user_id)
    roles = Role.query.order_by(Role.name).all()

    if request.method == 'POST':
        action = request.form.get('action', 'update')

        if action == 'reset_password':
            new_pw = request.form.get('new_password', '')
            if len(new_pw) < 8:
                flash('Password must be at least 8 characters.', 'danger')
            else:
                user.set_password(new_pw)
                db.session.commit()
                log_action('admin_password_reset', f'Admin reset password for {user.email}')
                flash('Password reset successfully.', 'success')
            return redirect(url_for('admin.users_edit', user_id=user.id))

        full_name = request.form.get('full_name', '').strip()
        if full_name:
            first, last = split_full_name(full_name)
            user.first_name = first
            user.last_name = last

        user.email = request.form.get('email', user.email).strip().lower()
        new_username = request.form.get('username', user.username).strip().lower()
        if new_username != user.username:
            if User.query.filter(User.username == new_username, User.id != user.id).first():
                flash('Username is already taken.', 'danger')
                return render_template('admin/users/form.html', roles=roles, user=user)
            user.username = new_username

        role_id = request.form.get('role_id', type=int)
        if role_id:
            user.role_id = role_id

        user.is_blocked = request.form.get('is_blocked') == 'on'
        user.phone = request.form.get('phone') or None
        user.gender = request.form.get('gender') or None
        dob = request.form.get('date_of_birth')
        user.date_of_birth = dob if dob else None

        db.session.commit()
        log_action('admin_user_update', f'Updated user {user.email}')
        flash('User updated successfully.', 'success')
        return redirect(url_for('admin.users_view', user_id=user.id))

    return render_template('admin/users/form.html', roles=roles, user=user)


@admin_bp.route('/users/<int:user_id>/toggle-block', methods=['POST'])
@login_required
@admin_required
def users_toggle_block(user_id):
    """Block or unblock a user account."""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot block your own account.', 'danger')
        return redirect(url_for('admin.users_view', user_id=user.id))

    user.is_blocked = not user.is_blocked
    db.session.commit()
    status = 'blocked' if user.is_blocked else 'unblocked'
    log_action('admin_user_block', f'User {user.email} {status}')
    flash(f'User {user.full_name} has been {status}.', 'success')
    return redirect(url_for('admin.users_view', user_id=user.id))


# ─── Researcher Management ───────────────────────────────────────────────────

@admin_bp.route('/researchers')
@login_required
@admin_required
def researchers_list():
    """List and manage researcher accounts."""
    search = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '')

    query = User.query.join(Role).filter(
        Role.name == 'researcher'
    ).order_by(desc(User.created_at))

    if search:
        like = f'%{search}%'
        query = query.filter(or_(
            User.username.ilike(like),
            User.email.ilike(like),
            User.first_name.ilike(like),
            User.last_name.ilike(like),
        ))
    if status_filter == 'blocked':
        query = query.filter(User.is_blocked.is_(True))
    elif status_filter == 'active':
        query = query.filter(User.is_blocked.is_(False))

    researchers, page, total, total_pages = _paginate(query)

    pub_counts = {}
    for r in researchers:
        pub_counts[r.id] = Publication.query.filter_by(author_id=r.id).count()

    return render_template(
        'admin/researchers/list.html',
        researchers=researchers, pub_counts=pub_counts,
        page=page, total=total, total_pages=total_pages,
        search=search, status_filter=status_filter,
    )


@admin_bp.route('/researchers/create', methods=['GET', 'POST'])
@login_required
@admin_required
def researchers_create():
    """Create a new researcher account."""
    researcher_role = Role.query.filter_by(name='researcher').first_or_404()
    roles = [researcher_role]

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if not username or not re.match(r'^[a-zA-Z0-9_]{3,30}$', username):
            errors.append('Username must be 3–30 characters.')
        if not email or not EMAIL_PATTERN.match(email):
            errors.append('A valid email is required.')
        if not password or len(password) < 8:
            errors.append('Password must be at least 8 characters.')

        if errors:
            for msg in errors:
                flash(msg, 'danger')
            return render_template('admin/users/form.html', roles=roles, user=None,
                                   back_url=url_for('admin.researchers_list'),
                                   create_label='Create Researcher')

        if User.query.filter_by(email=email).first():
            flash('Email is already registered.', 'danger')
            return render_template('admin/users/form.html', roles=roles, user=None,
                                   back_url=url_for('admin.researchers_list'),
                                   create_label='Create Researcher')
        if User.query.filter_by(username=username).first():
            flash('Username is already taken.', 'danger')
            return render_template('admin/users/form.html', roles=roles, user=None,
                                   back_url=url_for('admin.researchers_list'),
                                   create_label='Create Researcher')

        first_name, last_name = split_full_name(full_name)
        user = User(
            role_id=researcher_role.id,
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            email_verified=True,
            email_verified_at=datetime.utcnow(),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        log_action('admin_researcher_create', f'Created researcher {email}')
        flash(f'Researcher account created for {email}.', 'success')
        return redirect(url_for('admin.researchers_list'))

    return render_template('admin/users/form.html', roles=roles, user=None,
                           back_url=url_for('admin.researchers_list'),
                           create_label='Create Researcher')


# ─── Publications ────────────────────────────────────────────────────────────

@admin_bp.route('/publications')
@login_required
@admin_required
def publications_list():
    """List all publications with status filter."""
    status_filter = request.args.get('status', '')
    query = Publication.query.order_by(desc(Publication.created_at))
    if status_filter:
        query = query.filter_by(status=status_filter)
    publications, page, total, total_pages = _paginate(query)
    return render_template(
        'admin/publications/list.html',
        publications=publications, page=page, total=total,
        total_pages=total_pages, status_filter=status_filter,
    )


@admin_bp.route('/publications/create', methods=['GET', 'POST'])
@login_required
@admin_required
def publications_create():
    """Create a publication (admin can assign any author)."""
    researchers = User.query.join(Role).filter(
        Role.name.in_(['researcher', 'admin'])
    ).order_by(User.first_name).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Title is required.', 'danger')
            return render_template('admin/publications/form.html',
                                   publication=None, researchers=researchers)

        author_id = request.form.get('author_id', type=int) or current_user.id
        pub_date = request.form.get('date_published') or None

        pub = Publication(
            author_id=author_id,
            title=title,
            description=request.form.get('description', '').strip(),
            content=request.form.get('content', '').strip(),
            date_published=pub_date,
            status=request.form.get('status', 'draft'),
        )
        db.session.add(pub)
        db.session.commit()
        if pub.status == 'published':
            from app.utils.helpers import notify_users_publication
            notify_users_publication(pub)
        log_action('admin_publication_create', f'Created publication: {title}')
        flash('Publication created.', 'success')
        return redirect(url_for('admin.publications_list'))

    return render_template('admin/publications/form.html',
                           publication=None, researchers=researchers)


@admin_bp.route('/publications/<int:pub_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def publications_edit(pub_id):
    """Edit an existing publication."""
    pub = Publication.query.get_or_404(pub_id)
    researchers = User.query.join(Role).filter(
        Role.name.in_(['researcher', 'admin'])
    ).order_by(User.first_name).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Title is required.', 'danger')
            return render_template('admin/publications/form.html',
                                   publication=pub, researchers=researchers)

        previous_status = pub.status
        pub.title = title
        pub.description = request.form.get('description', '').strip()
        pub.content = request.form.get('content', '').strip()
        pub.status = request.form.get('status', pub.status)
        pub.author_id = request.form.get('author_id', type=int) or pub.author_id
        pub_date = request.form.get('date_published')
        pub.date_published = pub_date if pub_date else None

        db.session.commit()
        if pub.status == 'published' and previous_status != 'published':
            from app.utils.helpers import notify_users_publication
            notify_users_publication(pub)
        log_action('admin_publication_update', f'Updated publication: {title}')
        flash('Publication updated.', 'success')
        return redirect(url_for('admin.publications_list'))

    return render_template('admin/publications/form.html',
                           publication=pub, researchers=researchers)


@admin_bp.route('/publications/<int:pub_id>/delete', methods=['POST'])
@login_required
@admin_required
def publications_delete(pub_id):
    """Delete a publication."""
    pub = Publication.query.get_or_404(pub_id)
    title = pub.title
    db.session.delete(pub)
    db.session.commit()
    log_action('admin_publication_delete', f'Deleted publication: {title}')
    flash('Publication deleted.', 'success')
    return redirect(url_for('admin.publications_list'))


# ─── Feedback Requests ───────────────────────────────────────────────────────

@admin_bp.route('/feedback')
@login_required
@admin_required
def feedback_list():
    """List all feedback requests."""
    status_filter = request.args.get('status', '')
    query = FeedbackRequest.query.order_by(desc(FeedbackRequest.requested_at))
    if status_filter:
        query = query.filter_by(status=status_filter)
    requests_list, page, total, total_pages = _paginate(query)
    researchers = User.query.join(Role).filter(Role.name == 'researcher').all()
    return render_template(
        'admin/feedback/list.html',
        requests_list=requests_list, researchers=researchers,
        page=page, total=total, total_pages=total_pages,
        status_filter=status_filter,
    )


@admin_bp.route('/feedback/<int:req_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def feedback_view(req_id):
    """View and manage a feedback request."""
    fb_req = FeedbackRequest.query.get_or_404(req_id)
    researchers = User.query.join(Role).filter(Role.name == 'researcher').all()

    if request.method == 'POST':
        fb_req.status = request.form.get('status', fb_req.status)
        researcher_id = request.form.get('researcher_id', type=int)
        if researcher_id:
            fb_req.researcher_id = researcher_id
        if fb_req.status in ('completed', 'ignored'):
            fb_req.responded_at = datetime.utcnow()
        db.session.commit()
        log_action('admin_feedback_update', f'Updated feedback request #{req_id}')
        flash('Feedback request updated.', 'success')
        return redirect(url_for('admin.feedback_list'))

    return render_template('admin/feedback/view.html',
                           fb_req=fb_req, researchers=researchers)


# ─── Alerts ──────────────────────────────────────────────────────────────────

@admin_bp.route('/alerts')
@login_required
@admin_required
def alerts_list():
    """List system alerts."""
    severity_filter = request.args.get('severity', '')
    query = Alert.query.order_by(desc(Alert.created_at))
    if severity_filter:
        query = query.filter_by(severity=severity_filter)
    alerts, page, total, total_pages = _paginate(query)
    return render_template(
        'admin/alerts/list.html',
        alerts=alerts, page=page, total=total,
        total_pages=total_pages, severity_filter=severity_filter,
    )


@admin_bp.route('/alerts/<int:alert_id>/read', methods=['POST'])
@login_required
@admin_required
def alerts_mark_read(alert_id):
    """Mark an alert as read."""
    alert = Alert.query.get_or_404(alert_id)
    alert.is_read = True
    db.session.commit()
    flash('Alert marked as read.', 'success')
    return redirect(url_for('admin.alerts_list'))


# ─── Audit Logs ──────────────────────────────────────────────────────────────

@admin_bp.route('/logs')
@login_required
@admin_required
def logs_list():
    """View system audit logs with filters."""
    action_filter = request.args.get('action', '').strip()
    search = request.args.get('q', '').strip()

    query = SystemLog.query.order_by(desc(SystemLog.created_at))
    if action_filter:
        query = query.filter(SystemLog.action.ilike(f'%{action_filter}%'))
    if search:
        like = f'%{search}%'
        query = query.filter(or_(
            SystemLog.details.ilike(like),
            SystemLog.action.ilike(like),
        ))

    logs, page, total, total_pages = _paginate(query)
    action_types = db.session.query(
        SystemLog.action, func.count(SystemLog.id)
    ).group_by(SystemLog.action).order_by(desc(func.count(SystemLog.id))).limit(20).all()

    return render_template(
        'admin/logs/list.html',
        logs=logs, page=page, total=total, total_pages=total_pages,
        action_filter=action_filter, search=search, action_types=action_types,
    )


@admin_bp.route('/logs/export')
@login_required
@admin_required
def logs_export():
    """Export audit logs as CSV."""
    logs = SystemLog.query.order_by(desc(SystemLog.created_at)).limit(5000).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'User', 'Action', 'Details', 'IP', 'Timestamp'])
    for log in logs:
        writer.writerow([
            log.id,
            log.user.email if log.user else 'System',
            log.action,
            log.details or '',
            log.ip_address or '',
            log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else '',
        ])
    log_action('admin_logs_export', 'Exported audit logs to CSV')
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=audit_logs.csv'},
    )


# ─── Metrics Overview ────────────────────────────────────────────────────────

@admin_bp.route('/metrics')
@login_required
@admin_required
def metrics_overview():
    """Overview of all user assessment metrics."""
    search = request.args.get('q', '').strip()
    query = User.query.join(Role).filter(Role.name == 'user').order_by(User.first_name)

    if search:
        like = f'%{search}%'
        query = query.filter(or_(
            User.username.ilike(like),
            User.email.ilike(like),
            User.first_name.ilike(like),
            User.last_name.ilike(like),
        ))

    users, page, total, total_pages = _paginate(query)
    user_metrics = []
    for u in users:
        avg = get_user_averages(u.id)
        user_metrics.append({
            'user': u,
            'typing_attempts': get_attempt_count(u.id, 'typing'),
            'reaction_attempts': get_attempt_count(u.id, 'reaction'),
            'averages': avg,
        })

    total_completed = Task.query.filter_by(status='completed').count()
    avg_typing = db.session.query(
        func.avg(CognitiveMetrics.typing_speed_wpm)
    ).filter(CognitiveMetrics.typing_speed_wpm.isnot(None)).scalar()
    avg_reaction = db.session.query(
        func.avg(CognitiveMetrics.response_time_ms)
    ).filter(CognitiveMetrics.response_time_ms.isnot(None)).scalar()

    return render_template(
        'admin/metrics.html',
        user_metrics=user_metrics, page=page, total=total,
        total_pages=total_pages, search=search,
        total_completed=total_completed,
        avg_typing=round(float(avg_typing), 1) if avg_typing else None,
        avg_reaction=round(float(avg_reaction), 1) if avg_reaction else None,
    )


# ─── System Settings ─────────────────────────────────────────────────────────

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    """Manage system settings."""
    if request.method == 'POST':
        set_system_setting('site_name', request.form.get('site_name', '').strip())
        set_system_setting('contact_email', request.form.get('contact_email', '').strip())
        set_system_setting('assessments_per_cycle',
                           request.form.get('assessments_per_cycle', '5').strip())
        maintenance = '1' if request.form.get('maintenance_mode') == 'on' else '0'
        set_system_setting('maintenance_mode', maintenance)
        log_action('admin_settings_update', 'System settings updated')
        flash('Settings saved successfully.', 'success')
        return redirect(url_for('admin.settings'))

    settings_map = {
        'site_name': get_system_setting('site_name', 'CogMonitor'),
        'contact_email': get_system_setting('contact_email', ''),
        'assessments_per_cycle': get_system_setting('assessments_per_cycle', '5'),
        'maintenance_mode': get_system_setting('maintenance_mode', '0') == '1',
    }
    all_settings = SystemSettings.query.order_by(SystemSettings.setting_key).all()
    return render_template('admin/settings.html',
                           settings_map=settings_map, all_settings=all_settings)


# ─── Broadcast Notifications ─────────────────────────────────────────────────

@admin_bp.route('/notifications', methods=['GET', 'POST'])
@login_required
@admin_required
def notifications_broadcast():
    """Send system notification to all users or a specific role."""
    roles = Role.query.order_by(Role.name).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        message = request.form.get('message', '').strip()
        target_role = request.form.get('target_role', 'all')
        link_url = request.form.get('link_url', '').strip() or None

        if not title or not message:
            flash('Title and message are required.', 'danger')
            return render_template('admin/notifications.html', roles=roles)

        if target_role == 'all':
            recipients = User.query.filter_by(is_blocked=False).all()
        else:
            recipients = User.query.join(Role).filter(
                Role.name == target_role, User.is_blocked.is_(False)
            ).all()

        for u in recipients:
            notif = Notification(
                user_id=u.id,
                notification_type='system',
                title=title,
                message=message,
                link_url=link_url,
            )
            db.session.add(notif)
        db.session.commit()
        log_action('admin_notification_broadcast',
                   f'Sent "{title}" to {len(recipients)} users')
        flash(f'Notification sent to {len(recipients)} users.', 'success')
        return redirect(url_for('admin.notifications_broadcast'))

    return render_template('admin/notifications.html', roles=roles)
