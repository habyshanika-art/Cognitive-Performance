"""
User Dashboard Controller
-----------------------
Dashboard, assessments (typing/reaction/memory/concentration), results, consent,
profile email inbox, withdraw/delete data, and notifications.
"""

import json
from datetime import datetime

from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, jsonify, current_app
)
from flask_login import login_required, current_user
from sqlalchemy import desc

from app import db
from app.models.session import Session
from app.models.task import Task
from app.models.interaction_data import InteractionData
from app.models.cognitive_metrics import CognitiveMetrics
from app.models.publication import Publication
from app.models.feedback import Feedback
from app.models.feedback_request import FeedbackRequest
from app.models.notification import Notification
from app.models.email_message import EmailMessage
from app.models.aggregated_metrics import AggregatedMetrics
from app.models.alert import Alert
from app.utils.decorators import user_required
from app.utils.helpers import (
    generate_session_token, log_action,
    save_profile_picture, delete_profile_picture
)
from app.utils.metrics import (
    get_user_averages, get_typing_progress, get_reaction_progress,
    get_memory_progress, get_concentration_progress, get_results_feedback,
    can_attempt_assessment, get_next_attempt_number,
    get_attempt_count, finalize_cycle_if_complete,
    get_assessments_per_cycle, get_current_cycle,
    get_cycle_trend_chart, get_monitoring_status,
)
from app.utils.validation import (
    detect_device_type, validate_typing_attempt, validate_reaction_attempt,
    validate_memory_attempt, validate_concentration_attempt,
    summarize_mouse_metrics, build_validation_flags,
)
from app.utils.email_service import send_user_email, generate_password_reset_code

user_bp = Blueprint('user', __name__, url_prefix='/user')

CONSENT_EXEMPT = {
    'user.consent', 'user.withdraw_data', 'auth.logout', 'static',
}


@user_bp.before_request
def require_consent():
    """Block assessment/dashboard use until research consent is given."""
    if not current_user.is_authenticated:
        return
    if not current_user.is_regular_user():
        return
    if getattr(current_user, 'data_withdrawn', False):
        if request.endpoint not in ('user.withdraw_data', 'auth.logout', 'user.consent'):
            flash('Your data withdrawal is recorded. Contact admin to reactivate.', 'warning')
            return redirect(url_for('auth.logout'))
        return
    if getattr(current_user, 'consent_given', False):
        return
    if request.endpoint in CONSENT_EXEMPT or (request.endpoint or '').startswith('static'):
        return
    if request.endpoint and request.endpoint.startswith('user.'):
        # Assessment submit API expects JSON, not an HTML redirect
        if request.endpoint == 'user.submit_assessment' or (
            request.path.endswith('/submit') and request.method == 'POST'
        ):
            return jsonify({
                'success': False,
                'error': 'Consent required before assessments.',
                'consent_required': True,
            }), 403
        return redirect(url_for('user.consent'))


def _get_or_create_assessment_session():
    """Get active session or create one for assessment tracking."""
    sess = Session.query.filter_by(
        user_id=current_user.id, is_active=True
    ).order_by(desc(Session.started_at)).first()

    if not sess:
        sess = Session(
            user_id=current_user.id,
            session_token=generate_session_token(),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:255]
        )
        db.session.add(sess)
        db.session.commit()
    return sess


def _create_assessment_reminder_if_needed():
    """Create assessment reminder notification if attempts remain in current cycle."""
    if not getattr(current_user, 'notify_assessment_reminders', True):
        return

    max_attempts = get_assessments_per_cycle()
    typing_left = max_attempts - get_attempt_count(current_user.id, 'typing')
    reaction_left = max_attempts - get_attempt_count(current_user.id, 'reaction')
    memory_left = max_attempts - get_attempt_count(current_user.id, 'memory')
    concentration_left = max_attempts - get_attempt_count(current_user.id, 'concentration')

    if typing_left > 0 or reaction_left > 0 or memory_left > 0 or concentration_left > 0:
        existing = Notification.query.filter_by(
            user_id=current_user.id,
            notification_type='assessment_reminder',
            is_read=False
        ).first()
        if not existing:
            msg_parts = []
            if typing_left > 0:
                msg_parts.append(f'{typing_left} typing test(s)')
            if reaction_left > 0:
                msg_parts.append(f'{reaction_left} reaction test(s)')
            if memory_left > 0:
                msg_parts.append(f'{memory_left} memory test(s)')
            if concentration_left > 0:
                msg_parts.append(f'{concentration_left} concentration test(s)')
            notif = Notification(
                user_id=current_user.id,
                notification_type='assessment_reminder',
                title='Assessment Reminder',
                message=f'You have {" and ".join(msg_parts)} remaining.',
                link_url='/user/assessments'
            )
            db.session.add(notif)
            db.session.commit()


@user_bp.route('/consent', methods=['GET', 'POST'])
@login_required
@user_required
def consent():
    """Research consent + not-a-diagnosis disclaimer."""
    version = current_app.config.get('CONSENT_VERSION', '1.0')
    if request.method == 'POST':
        if request.form.get('agree') != 'on':
            flash('You must accept the consent terms to continue.', 'danger')
            return render_template('user/consent.html', consent_version=version)

        current_user.consent_given = True
        current_user.consent_given_at = datetime.utcnow()
        current_user.consent_version = version
        current_user.ensure_anonymised_id()
        db.session.commit()
        log_action('consent_accepted', f'Consent v{version} accepted')
        try:
            send_user_email(
                current_user,
                'Consent recorded — CogMonitor',
                (
                    f'Hello {current_user.first_name},\n\n'
                    f'Your research consent (version {version}) was recorded on '
                    f'{datetime.utcnow().strftime("%Y-%m-%d %H:%M")} UTC.\n'
                    f'Your anonymised research ID is {current_user.display_id}.\n\n'
                    'Important: CogMonitor monitors interaction patterns for research. '
                    'It does NOT provide a medical diagnosis.\n\n'
                    'You may withdraw and request deletion of your data anytime from Settings.\n'
                ),
                category='consent',
            )
        except Exception:
            pass
        flash('Thank you. Consent saved. Remember: this system is not a diagnosis.', 'success')
        return redirect(url_for('user.dashboard'))

    return render_template('user/consent.html', consent_version=version)


@user_bp.route('/dashboard')
@login_required
@user_required
def dashboard():
    """Main user dashboard with stats, charts, publications, notifications."""
    averages = get_user_averages(current_user.id)
    typing_chart = get_typing_progress(current_user.id)
    reaction_chart = get_reaction_progress(current_user.id)
    memory_chart = get_memory_progress(current_user.id)
    concentration_chart = get_concentration_progress(current_user.id)
    cycle_chart = get_cycle_trend_chart(current_user.id)
    monitoring = get_monitoring_status(current_user.id)

    total_assessments = (
        averages.get('typing_attempts', 0)
        + averages.get('reaction_attempts', 0)
        + averages.get('memory_attempts', 0)
        + averages.get('concentration_attempts', 0)
    )

    latest_feedback = Feedback.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(Feedback.sent_at)).first()

    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(Notification.created_at)).limit(10).all()

    publications = Publication.query.filter_by(
        status='published'
    ).order_by(desc(Publication.date_published)).limit(3).all()

    _create_assessment_reminder_if_needed()

    return render_template(
        'user/dashboard.html',
        total_assessments=total_assessments,
        averages=averages,
        latest_feedback=latest_feedback,
        notifications=notifications,
        publications=publications,
        typing_chart=json.dumps(typing_chart),
        reaction_chart=json.dumps(reaction_chart),
        memory_chart=json.dumps(memory_chart),
        concentration_chart=json.dumps(concentration_chart),
        cycle_chart=json.dumps(cycle_chart),
        monitoring=monitoring,
    )


@user_bp.route('/assessments')
@login_required
@user_required
def assessments():
    """List available cognitive assessments with cycle-based progress."""
    max_attempts = get_assessments_per_cycle()
    cycle = get_current_cycle(current_user.id)
    typing_attempts = get_attempt_count(current_user.id, 'typing')
    reaction_attempts = get_attempt_count(current_user.id, 'reaction')
    memory_attempts = get_attempt_count(current_user.id, 'memory')
    concentration_attempts = get_attempt_count(current_user.id, 'concentration')
    monitoring = get_monitoring_status(current_user.id)

    return render_template(
        'user/assessments.html',
        typing_attempts=typing_attempts,
        reaction_attempts=reaction_attempts,
        memory_attempts=memory_attempts,
        concentration_attempts=concentration_attempts,
        max_attempts=max_attempts,
        current_cycle=cycle,
        monitoring=monitoring,
    )


@user_bp.route('/assessments/typing')
@login_required
@user_required
def typing_test():
    """Typing speed test page."""
    practice = request.args.get('practice') == '1'
    if not practice and not can_attempt_assessment(current_user.id, 'typing'):
        flash(f'You have completed all {get_assessments_per_cycle()} typing attempts for this cycle.', 'warning')
        return redirect(url_for('user.assessments'))
    return render_template(
        'user/typing_test.html',
        attempt_number=get_next_attempt_number(current_user.id, 'typing'),
        is_practice=practice,
    )


@user_bp.route('/assessments/reaction')
@login_required
@user_required
def reaction_test():
    """Reaction time test page."""
    practice = request.args.get('practice') == '1'
    if not practice and not can_attempt_assessment(current_user.id, 'reaction'):
        flash(f'You have completed all {get_assessments_per_cycle()} reaction attempts for this cycle.', 'warning')
        return redirect(url_for('user.assessments'))
    return render_template(
        'user/reaction_test.html',
        attempt_number=get_next_attempt_number(current_user.id, 'reaction'),
        is_practice=practice,
    )


@user_bp.route('/assessments/memory')
@login_required
@user_required
def memory_test():
    """Short-term memory digit-sequence task."""
    practice = request.args.get('practice') == '1'
    if not practice and not can_attempt_assessment(current_user.id, 'memory'):
        flash(f'You have completed all {get_assessments_per_cycle()} memory attempts for this cycle.', 'warning')
        return redirect(url_for('user.assessments'))
    return render_template(
        'user/memory_test.html',
        attempt_number=get_next_attempt_number(current_user.id, 'memory'),
        is_practice=practice,
    )


@user_bp.route('/assessments/concentration')
@login_required
@user_required
def concentration_test():
    """Sustained attention / concentration go-no-go task."""
    practice = request.args.get('practice') == '1'
    if not practice and not can_attempt_assessment(current_user.id, 'concentration'):
        flash(
            f'You have completed all {get_assessments_per_cycle()} '
            'concentration attempts for this cycle.',
            'warning',
        )
        return redirect(url_for('user.assessments'))
    return render_template(
        'user/concentration_test.html',
        attempt_number=get_next_attempt_number(current_user.id, 'concentration'),
        is_practice=practice,
    )


@user_bp.route('/api/submit-assessment', methods=['POST'])
@login_required
@user_required
def submit_assessment():
    """API endpoint to save assessment results from JavaScript tests."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid data'}), 400

    task_type = data.get('task_type')
    if task_type not in ('typing', 'reaction', 'memory', 'concentration'):
        return jsonify({'error': 'Invalid task type'}), 400

    is_practice = bool(data.get('is_practice'))
    if not can_attempt_assessment(current_user.id, task_type, practice=is_practice):
        return jsonify({'error': 'Maximum attempts reached'}), 400

    # Validate
    if task_type == 'typing':
        ok, errors, cleaned = validate_typing_attempt(data)
    elif task_type == 'reaction':
        ok, errors, cleaned = validate_reaction_attempt(data)
        if ok and cleaned.get('response_time_ms'):
            data['response_time_ms'] = cleaned['response_time_ms']
            data['score'] = max(0, round(100 - cleaned['response_time_ms'] / 10))
    elif task_type == 'memory':
        ok, errors, cleaned = validate_memory_attempt(data)
    else:
        ok, errors, cleaned = validate_concentration_attempt(data)

    device = detect_device_type(request.headers.get('User-Agent', ''))
    mouse_summary = summarize_mouse_metrics(data.get('raw_events'))
    flags = build_validation_flags(errors, {
        'cleaned': cleaned,
        'mouse': mouse_summary,
        'device_type': device,
    })

    if not ok and not is_practice:
        # Store rejected attempt for audit, do not consume a valid attempt number
        sess = _get_or_create_assessment_session()
        cycle = get_current_cycle(current_user.id)
        task = Task(
            session_id=sess.id,
            user_id=current_user.id,
            task_type=task_type,
            attempt_number=0,
            cycle_number=cycle,
            completed_at=datetime.utcnow(),
            completion_time_ms=data.get('time_taken_ms', 0),
            score=data.get('score', 0),
            status='rejected',
            device_type=device,
            is_practice=False,
            is_valid=False,
            validation_flags=flags,
        )
        db.session.add(task)
        db.session.commit()
        log_action('assessment_rejected', f'{task_type}: {"; ".join(errors)}')
        return jsonify({'error': errors[0], 'errors': errors, 'rejected': True}), 400

    score = data.get('score', 0)
    time_taken_ms = data.get('time_taken_ms', 0)
    typing_wpm = data.get('typing_speed_wpm')
    response_ms = data.get('response_time_ms')
    memory_score = data.get('memory_score', score if task_type == 'memory' else None)
    concentration_score = data.get(
        'concentration_score', score if task_type == 'concentration' else None
    )
    error_rate = data.get('error_rate', 0)

    sess = _get_or_create_assessment_session()
    cycle = get_current_cycle(current_user.id)
    attempt_num = 0 if is_practice else get_next_attempt_number(current_user.id, task_type)

    raw_events = data.get('raw_events') or {}
    raw_events['mouse'] = mouse_summary
    raw_events['validation'] = cleaned

    task = Task(
        session_id=sess.id,
        user_id=current_user.id,
        task_type=task_type,
        attempt_number=max(attempt_num, 1),
        cycle_number=cycle,
        completed_at=datetime.utcnow(),
        completion_time_ms=time_taken_ms,
        score=score,
        status='completed',
        device_type=device,
        is_practice=is_practice,
        is_valid=True,
        validation_flags=flags,
    )
    db.session.add(task)
    db.session.flush()

    interaction = InteractionData(
        task_id=task.id,
        user_id=current_user.id,
        session_id=sess.id,
        typing_speed_wpm=typing_wpm,
        response_time_ms=response_ms,
        task_completion_time_ms=time_taken_ms,
        error_rate=error_rate,
        event_type='assessment_complete',
        event_data=raw_events,
    )
    db.session.add(interaction)

    if not is_practice:
        metric = CognitiveMetrics(
            user_id=current_user.id,
            task_id=task.id,
            task_type=task_type,
            attempt_number=attempt_num,
            cycle_number=cycle,
            typing_speed_wpm=typing_wpm,
            response_time_ms=response_ms,
            memory_score=memory_score,
            concentration_score=concentration_score,
            error_rate=error_rate,
        )
        db.session.add(metric)

    db.session.commit()

    if not is_practice:
        finalize_cycle_if_complete(current_user.id)

    log_action(
        'assessment_complete',
        f'{task_type} attempt {attempt_num} practice={is_practice} score={score} device={device}',
        current_user.id,
    )

    return jsonify({
        'success': True,
        'attempt_number': attempt_num,
        'score': float(score),
        'is_practice': is_practice,
        'device_type': device,
        'redirect': url_for('user.results'),
    })


@user_bp.route('/results')
@login_required
@user_required
def results():
    """Display user's assessment results and cognitive metrics."""
    averages = get_user_averages(current_user.id)
    cycle = get_current_cycle(current_user.id)
    typing_metrics = CognitiveMetrics.query.filter_by(
        user_id=current_user.id, task_type='typing', cycle_number=cycle,
    ).order_by(CognitiveMetrics.attempt_number).all()
    reaction_metrics = CognitiveMetrics.query.filter_by(
        user_id=current_user.id, task_type='reaction', cycle_number=cycle,
    ).order_by(CognitiveMetrics.attempt_number).all()
    memory_metrics = CognitiveMetrics.query.filter_by(
        user_id=current_user.id, task_type='memory', cycle_number=cycle,
    ).order_by(CognitiveMetrics.attempt_number).all()
    concentration_metrics = CognitiveMetrics.query.filter_by(
        user_id=current_user.id, task_type='concentration', cycle_number=cycle,
    ).order_by(CognitiveMetrics.attempt_number).all()
    cycle_chart = get_cycle_trend_chart(current_user.id)
    monitoring = get_monitoring_status(current_user.id)

    return render_template(
        'user/results.html',
        averages=averages,
        feedback=get_results_feedback(averages),
        typing_metrics=typing_metrics,
        reaction_metrics=reaction_metrics,
        memory_metrics=memory_metrics,
        concentration_metrics=concentration_metrics,
        cycle_chart=json.dumps(cycle_chart),
        monitoring=monitoring,
    )


@user_bp.route('/request-feedback', methods=['GET', 'POST'])
@login_required
@user_required
def request_feedback():
    """Submit a request for researcher feedback."""
    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        if not message:
            flash('Please enter a message for the researcher.', 'danger')
            return render_template('user/request_feedback.html')

        req = FeedbackRequest(
            user_id=current_user.id,
            user_message=message,
            status='pending'
        )
        db.session.add(req)
        db.session.commit()
        log_action('feedback_request', f'Feedback requested: {message[:50]}')
        flash('Your feedback request has been submitted.', 'success')
        return redirect(url_for('user.request_feedback'))

    requests_list = FeedbackRequest.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(FeedbackRequest.requested_at)).all()

    return render_template('user/request_feedback.html', requests_list=requests_list)


@user_bp.route('/publications')
@login_required
@user_required
def publications():
    """Browse research publications from researchers."""
    pubs = Publication.query.filter_by(
        status='published'
    ).order_by(desc(Publication.date_published)).all()
    return render_template('user/publications.html', publications=pubs)


@user_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@user_required
def profile():
    """View and edit user profile, change password, upload picture."""
    if request.method == 'POST':
        action = request.form.get('action', 'update_profile')

        if action == 'change_password':
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')

            if not current_user.check_password(current_pw):
                flash('Current password is incorrect.', 'danger')
            elif len(new_pw) < 8:
                flash('New password must be at least 8 characters.', 'danger')
            elif new_pw != confirm_pw:
                flash('New passwords do not match.', 'danger')
            else:
                current_user.set_password(new_pw)
                db.session.commit()
                log_action('password_change', 'User changed password')
                send_user_email(
                    current_user,
                    'Password changed — CogMonitor',
                    (
                        f'Hello {current_user.first_name},\n\n'
                        f'Your CogMonitor password was changed successfully.\n'
                        f'If this was not you, request a reset code immediately.\n'
                    ),
                    category='system',
                )
                flash('Password updated successfully.', 'success')
            return redirect(url_for('user.profile'))

        if action == 'request_password_code':
            try:
                code = generate_password_reset_code(current_user)
                flash(
                    f'A password reset code was sent to your email inbox '
                    f'(and SMTP if configured). Code also stored under Email: {code}',
                    'success',
                )
            except Exception:
                flash('Could not generate a reset code. Please try again.', 'danger')
            return redirect(url_for('user.emails'))

        full_name = request.form.get('full_name', '').strip()
        if full_name:
            from app.utils.helpers import split_full_name
            first, last = split_full_name(full_name)
            current_user.first_name = first
            current_user.last_name = last

        # Allow updating contact email (unique)
        new_email = request.form.get('email', '').strip().lower()
        if new_email and new_email != current_user.email:
            from app.models.user import User
            if User.query.filter(User.email == new_email, User.id != current_user.id).first():
                flash('That email is already in use.', 'danger')
                return redirect(url_for('user.profile'))
            current_user.email = new_email
            send_user_email(
                current_user,
                'Email updated — CogMonitor',
                f'Your account email is now {new_email}. Notifications will use this address.',
                category='system',
            )

        current_user.date_of_birth = request.form.get('date_of_birth') or None
        current_user.gender = request.form.get('gender') or None
        current_user.phone = request.form.get('phone') or None

        new_picture = save_profile_picture(request.files.get('profile_picture'))
        if new_picture:
            delete_profile_picture(current_user.profile_picture)
            current_user.profile_picture = new_picture

        db.session.commit()
        log_action('profile_update', 'User updated profile')
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('user.profile'))

    unread_emails = current_user.unread_email_count()
    return render_template('user/profile.html', unread_emails=unread_emails)


@user_bp.route('/emails')
@login_required
@user_required
def emails():
    """In-app email inbox (notifications, codes, alerts)."""
    messages = EmailMessage.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(EmailMessage.created_at)).all()
    return render_template('user/emails.html', messages=messages)


@user_bp.route('/emails/<int:message_id>')
@login_required
@user_required
def email_detail(message_id):
    msg = EmailMessage.query.filter_by(
        id=message_id, user_id=current_user.id
    ).first_or_404()
    msg.is_read = True
    db.session.commit()
    return render_template('user/email_detail.html', message=msg)


@user_bp.route('/emails/<int:message_id>/read', methods=['POST'])
@login_required
@user_required
def mark_email_read(message_id):
    msg = EmailMessage.query.filter_by(
        id=message_id, user_id=current_user.id
    ).first_or_404()
    msg.is_read = True
    db.session.commit()
    return jsonify({'success': True})


@user_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@user_required
def settings():
    """User notification and privacy preferences."""
    if request.method == 'POST':
        current_user.notify_assessment_reminders = (
            request.form.get('notify_assessment_reminders') == 'on'
        )
        current_user.notify_performance_alerts = (
            request.form.get('notify_performance_alerts') == 'on'
        )
        current_user.notify_publications = (
            request.form.get('notify_publications') == 'on'
        )
        current_user.notify_email = (
            request.form.get('notify_email') == 'on'
        )
        db.session.commit()
        log_action('settings_update', 'User updated notification preferences')
        flash('Settings saved successfully.', 'success')
        return redirect(url_for('user.settings'))

    return render_template('user/settings.html')


@user_bp.route('/withdraw-data', methods=['GET', 'POST'])
@login_required
@user_required
def withdraw_data():
    """Withdraw consent and delete personal assessment data."""
    if request.method == 'POST':
        confirm = request.form.get('confirm_text', '').strip().upper()
        if confirm != 'DELETE':
            flash('Type DELETE to confirm withdrawal and data deletion.', 'danger')
            return render_template('user/withdraw.html')

        uid = current_user.id
        # Delete assessment-related personal data
        InteractionData.query.filter_by(user_id=uid).delete()
        CognitiveMetrics.query.filter_by(user_id=uid).delete()
        Task.query.filter_by(user_id=uid).delete()
        AggregatedMetrics.query.filter_by(user_id=uid).delete()
        Alert.query.filter_by(user_id=uid).delete()
        Notification.query.filter_by(user_id=uid).delete()
        EmailMessage.query.filter_by(user_id=uid).delete()
        Feedback.query.filter_by(user_id=uid).delete()
        FeedbackRequest.query.filter_by(user_id=uid).delete()

        current_user.data_withdrawn = True
        current_user.consent_given = False
        current_user.first_name = 'Withdrawn'
        current_user.last_name = 'User'
        current_user.phone = None
        current_user.profile_picture = None
        # Keep anonymised_id and hashed credentials for audit integrity
        db.session.commit()
        log_action('data_withdrawn', 'User withdrew consent and deleted assessment data', uid)
        flash('Your assessment data has been deleted and consent withdrawn.', 'info')
        return redirect(url_for('auth.logout'))

    return render_template('user/withdraw.html')


@user_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
@user_required
def mark_notification_read(notification_id):
    """Mark a notification as read."""
    notif = Notification.query.filter_by(
        id=notification_id, user_id=current_user.id
    ).first_or_404()
    notif.is_read = True
    db.session.commit()
    return jsonify({'success': True})
