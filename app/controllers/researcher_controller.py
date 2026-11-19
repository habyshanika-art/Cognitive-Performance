"""
Researcher Dashboard Controller
-------------------------------
Researcher module: dashboard, view participant results,
provide feedback, and publish research articles.
"""

import csv
import io
import json
from datetime import datetime

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
    Response, make_response
)
from flask_login import login_required, current_user
from sqlalchemy import desc, or_

from app import db
from app.models.user import User
from app.models.role import Role
from app.models.task import Task
from app.models.cognitive_metrics import CognitiveMetrics
from app.models.publication import Publication
from app.models.feedback_request import FeedbackRequest
from app.models.feedback import Feedback
from app.models.notification import Notification
from app.models.alert import Alert
from app.models.aggregated_metrics import AggregatedMetrics
from app.models.analytics_report import AnalyticsReport
from app.utils.decorators import researcher_required
from app.utils.helpers import log_action
from app.utils.metrics import (
    get_user_averages, get_attempt_count,
    get_typing_progress, get_reaction_progress, get_memory_progress,
    get_concentration_progress,
    get_results_feedback,
    get_cycle_trend_chart, get_monitoring_status, get_current_cycle,
    build_participant_export_rows,
)
from app.utils.monitoring import generate_cohort_analytics
from app.utils.email_service import send_user_email

researcher_bp = Blueprint('researcher', __name__, url_prefix='/researcher')

PER_PAGE = 15


def _paginate(query):
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    total = query.count()
    items = query.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    return items, page, total, total_pages


@researcher_bp.route('/dashboard')
@login_required
@researcher_required
def dashboard():
    """Researcher overview: stats, pending feedback, publications."""
    pending_requests = FeedbackRequest.query.filter(
        FeedbackRequest.status == 'pending',
        or_(
            FeedbackRequest.researcher_id.is_(None),
            FeedbackRequest.researcher_id == current_user.id,
        )
    ).order_by(desc(FeedbackRequest.requested_at)).limit(5).all()

    my_feedback_count = Feedback.query.filter_by(
        researcher_id=current_user.id
    ).count()
    pending_count = FeedbackRequest.query.filter(
        FeedbackRequest.status == 'pending',
        or_(
            FeedbackRequest.researcher_id.is_(None),
            FeedbackRequest.researcher_id == current_user.id,
        )
    ).count()

    participant_count = User.query.join(Role).filter(Role.name == 'user').count()
    my_publications = Publication.query.filter_by(
        author_id=current_user.id
    ).order_by(desc(Publication.updated_at)).limit(3).all()
    published_count = Publication.query.filter_by(
        author_id=current_user.id, status='published'
    ).count()

    recent_participants = User.query.join(Role).filter(
        Role.name == 'user'
    ).order_by(desc(User.created_at)).limit(5).all()

    recent_alerts = Alert.query.order_by(desc(Alert.created_at)).limit(5).all()
    unread_alerts = Alert.query.filter_by(is_read=False).count()

    return render_template(
        'researcher/dashboard.html',
        pending_requests=pending_requests,
        pending_count=pending_count,
        my_feedback_count=my_feedback_count,
        participant_count=participant_count,
        published_count=published_count,
        my_publications=my_publications,
        recent_participants=recent_participants,
        recent_alerts=recent_alerts,
        unread_alerts=unread_alerts,
    )


# ─── View User Results ───────────────────────────────────────────────────────

@researcher_bp.route('/participants')
@login_required
@researcher_required
def participants_list():
    """List participants with anonymised IDs (no names/emails)."""
    search = request.args.get('q', '').strip()
    query = User.query.join(Role).filter(
        Role.name == 'user',
        User.data_withdrawn.is_(False),
    ).order_by(User.anonymised_id)

    if search:
        like = f'%{search}%'
        query = query.filter(User.anonymised_id.ilike(like))

    users, page, total, total_pages = _paginate(query)
    summaries = []
    for u in users:
        u.ensure_anonymised_id()
        avg = get_user_averages(u.id)
        summaries.append({
            'user': u,
            'typing_attempts': get_attempt_count(u.id, 'typing'),
            'reaction_attempts': get_attempt_count(u.id, 'reaction'),
            'memory_attempts': get_attempt_count(u.id, 'memory'),
            'concentration_attempts': get_attempt_count(u.id, 'concentration'),
            'averages': avg,
        })
    db.session.commit()

    return render_template(
        'researcher/participants/list.html',
        summaries=summaries, page=page, total=total,
        total_pages=total_pages, search=search,
    )


@researcher_bp.route('/participants/<int:user_id>/results')
@login_required
@researcher_required
def participant_results(user_id):
    """View detailed cognitive results for a participant (anonymised)."""
    user = User.query.join(Role).filter(
        User.id == user_id, Role.name == 'user'
    ).first_or_404()
    user.ensure_anonymised_id()
    db.session.commit()

    averages = get_user_averages(user.id)
    cycle = get_current_cycle(user.id)
    typing_metrics = CognitiveMetrics.query.filter_by(
        user_id=user.id, task_type='typing', cycle_number=cycle,
    ).order_by(CognitiveMetrics.attempt_number).all()
    reaction_metrics = CognitiveMetrics.query.filter_by(
        user_id=user.id, task_type='reaction', cycle_number=cycle,
    ).order_by(CognitiveMetrics.attempt_number).all()
    memory_metrics = CognitiveMetrics.query.filter_by(
        user_id=user.id, task_type='memory', cycle_number=cycle,
    ).order_by(CognitiveMetrics.attempt_number).all()
    concentration_metrics = CognitiveMetrics.query.filter_by(
        user_id=user.id, task_type='concentration', cycle_number=cycle,
    ).order_by(CognitiveMetrics.attempt_number).all()
    recent_tasks = Task.query.filter_by(user_id=user.id).order_by(
        desc(Task.completed_at)
    ).limit(10).all()
    cycle_history = AggregatedMetrics.query.filter_by(
        user_id=user.id,
    ).order_by(AggregatedMetrics.cycle_number).all()
    user_alerts = Alert.query.filter_by(user_id=user.id).order_by(
        desc(Alert.created_at)
    ).limit(10).all()
    monitoring = get_monitoring_status(user.id)

    return render_template(
        'researcher/participants/results.html',
        user=user,
        averages=averages,
        feedback=get_results_feedback(averages),
        typing_metrics=typing_metrics,
        reaction_metrics=reaction_metrics,
        memory_metrics=memory_metrics,
        concentration_metrics=concentration_metrics,
        recent_tasks=recent_tasks,
        cycle_history=cycle_history,
        user_alerts=user_alerts,
        monitoring=monitoring,
        current_cycle=cycle,
        typing_chart=json.dumps(get_typing_progress(user.id)),
        reaction_chart=json.dumps(get_reaction_progress(user.id)),
        memory_chart=json.dumps(get_memory_progress(user.id)),
        concentration_chart=json.dumps(get_concentration_progress(user.id)),
        cycle_chart=json.dumps(get_cycle_trend_chart(user.id)),
    )


@researcher_bp.route('/participants/<int:user_id>/export.csv')
@login_required
@researcher_required
def participant_export_csv(user_id):
    """CSV export of cycle metrics, deviations, and flags (anonymised)."""
    user = User.query.join(Role).filter(
        User.id == user_id, Role.name == 'user'
    ).first_or_404()
    user.ensure_anonymised_id()
    db.session.commit()

    rows = build_participant_export_rows(user.id)
    output = io.StringIO()
    fieldnames = [
        'participant_id', 'cycle', 'avg_typing_wpm', 'avg_reaction_ms',
        'avg_memory_score', 'avg_concentration_score', 'overall_score',
        'typing_deviation', 'reaction_deviation', 'memory_deviation',
        'concentration_deviation', 'overall_deviation',
        'is_baseline', 'is_flagged', 'calculated_at',
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    log_action('export_csv', f'Exported {user.display_id}', current_user.id)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition':
                f'attachment; filename=participant_{user.display_id}_cycles.csv'
        },
    )


@researcher_bp.route('/participants/<int:user_id>/export.pdf')
@login_required
@researcher_required
def participant_export_pdf(user_id):
    """Simple printable HTML report (save as PDF from browser)."""
    user = User.query.join(Role).filter(
        User.id == user_id, Role.name == 'user'
    ).first_or_404()
    user.ensure_anonymised_id()
    db.session.commit()

    rows = build_participant_export_rows(user.id)
    monitoring = get_monitoring_status(user.id)
    html = render_template(
        'researcher/participants/export_report.html',
        user=user,
        rows=rows,
        monitoring=monitoring,
        generated_at=datetime.utcnow(),
    )
    log_action('export_pdf', f'Report {user.display_id}', current_user.id)
    response = make_response(html)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response


# ─── Provide Feedback ────────────────────────────────────────────────────────

@researcher_bp.route('/feedback')
@login_required
@researcher_required
def feedback_list():
    """List feedback requests available to this researcher."""
    status_filter = request.args.get('status', 'pending')
    query = FeedbackRequest.query.order_by(desc(FeedbackRequest.requested_at))

    if status_filter:
        query = query.filter_by(status=status_filter)

    if status_filter == 'pending':
        query = query.filter(or_(
            FeedbackRequest.researcher_id.is_(None),
            FeedbackRequest.researcher_id == current_user.id,
        ))
    else:
        query = query.filter(
            or_(
                FeedbackRequest.researcher_id == current_user.id,
                FeedbackRequest.researcher_id.is_(None),
            )
        )

    requests_list, page, total, total_pages = _paginate(query)
    return render_template(
        'researcher/feedback/list.html',
        requests_list=requests_list, page=page, total=total,
        total_pages=total_pages, status_filter=status_filter,
    )


@researcher_bp.route('/feedback/<int:req_id>/respond', methods=['GET', 'POST'])
@login_required
@researcher_required
def feedback_respond(req_id):
    """Respond to a user's feedback request."""
    fb_req = FeedbackRequest.query.get_or_404(req_id)

    if (
        fb_req.researcher_id
        and fb_req.researcher_id != current_user.id
        and fb_req.status != 'pending'
    ):
        flash('This feedback request is assigned to another researcher.', 'danger')
        return redirect(url_for('researcher.feedback_list'))

    if fb_req.status == 'completed' and fb_req.feedback:
        return render_template(
            'researcher/feedback/respond.html',
            fb_req=fb_req, already_responded=True,
        )

    if request.method == 'POST':
        if fb_req.researcher_id and fb_req.researcher_id != current_user.id:
            flash('This feedback request is assigned to another researcher.', 'danger')
            return redirect(url_for('researcher.feedback_list'))

        content = request.form.get('content', '').strip()
        if not content:
            flash('Please enter your feedback response.', 'danger')
            return render_template(
                'researcher/feedback/respond.html',
                fb_req=fb_req, already_responded=False,
            )

        if fb_req.feedback:
            fb_req.feedback.content = content
            fb_req.feedback.researcher_id = current_user.id
        else:
            feedback = Feedback(
                feedback_request_id=fb_req.id,
                researcher_id=current_user.id,
                user_id=fb_req.user_id,
                content=content,
            )
            db.session.add(feedback)

        fb_req.status = 'completed'
        fb_req.researcher_id = current_user.id
        fb_req.responded_at = datetime.utcnow()

        notif = Notification(
            user_id=fb_req.user_id,
            notification_type='feedback',
            title='Researcher Feedback Received',
            message='A researcher has responded to your feedback request.',
            link_url='/user/request-feedback',
        )
        db.session.add(notif)
        db.session.commit()

        participant = User.query.get(fb_req.user_id)
        if participant:
            send_user_email(
                participant,
                'Researcher feedback received — CogMonitor',
                (
                    f'Hello {participant.first_name},\n\n'
                    f'A researcher has responded to your feedback request.\n\n'
                    f'---\n{content[:1500]}\n---\n\n'
                    f'This is research feedback only — not a medical diagnosis.\n'
                    f'Sign in to CogMonitor to view the full response.\n'
                ),
                category='notification',
                also_notify=False,
                link_url='/user/request-feedback',
            )

        log_action('researcher_feedback',
                   f'Feedback provided for request #{req_id}', current_user.id)
        flash('Feedback sent to the participant.', 'success')
        return redirect(url_for('researcher.feedback_list'))

    # Assign researcher when viewing
    if not fb_req.researcher_id:
        fb_req.researcher_id = current_user.id
        if fb_req.status == 'pending':
            fb_req.status = 'accepted'
        db.session.commit()

    user_averages = get_user_averages(fb_req.user_id) if fb_req.user_id else {}

    return render_template(
        'researcher/feedback/respond.html',
        fb_req=fb_req,
        already_responded=False,
        user_averages=user_averages,
    )


# ─── Publish Research Articles ───────────────────────────────────────────────

@researcher_bp.route('/publications')
@login_required
@researcher_required
def publications_list():
    """List researcher's own publications."""
    status_filter = request.args.get('status', '')
    query = Publication.query.filter_by(
        author_id=current_user.id
    ).order_by(desc(Publication.updated_at))
    if status_filter:
        query = query.filter_by(status=status_filter)
    publications, page, total, total_pages = _paginate(query)
    return render_template(
        'researcher/publications/list.html',
        publications=publications, page=page, total=total,
        total_pages=total_pages, status_filter=status_filter,
    )


@researcher_bp.route('/publications/create', methods=['GET', 'POST'])
@login_required
@researcher_required
def publications_create():
    """Create a new research article."""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Title is required.', 'danger')
            return render_template('researcher/publications/form.html', publication=None)

        pub_date = request.form.get('date_published') or None
        pub = Publication(
            author_id=current_user.id,
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
        log_action('researcher_publication_create', f'Created: {title}', current_user.id)
        flash('Article saved.', 'success')
        return redirect(url_for('researcher.publications_list'))

    return render_template('researcher/publications/form.html', publication=None)


@researcher_bp.route('/publications/<int:pub_id>/edit', methods=['GET', 'POST'])
@login_required
@researcher_required
def publications_edit(pub_id):
    """Edit own publication."""
    pub = Publication.query.filter_by(
        id=pub_id, author_id=current_user.id
    ).first_or_404()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Title is required.', 'danger')
            return render_template('researcher/publications/form.html', publication=pub)

        was_published = pub.status == 'published'
        pub.title = title
        pub.description = request.form.get('description', '').strip()
        pub.content = request.form.get('content', '').strip()
        pub.status = request.form.get('status', pub.status)
        pub_date = request.form.get('date_published')
        pub.date_published = pub_date if pub_date else None

        db.session.commit()
        if pub.status == 'published' and not was_published:
            from app.utils.helpers import notify_users_publication
            notify_users_publication(pub)
        log_action('researcher_publication_update', f'Updated: {title}', current_user.id)
        flash('Article updated.', 'success')
        return redirect(url_for('researcher.publications_list'))

    return render_template('researcher/publications/form.html', publication=pub)


@researcher_bp.route('/publications/<int:pub_id>/delete', methods=['POST'])
@login_required
@researcher_required
def publications_delete(pub_id):
    """Delete own publication."""
    pub = Publication.query.filter_by(
        id=pub_id, author_id=current_user.id
    ).first_or_404()
    title = pub.title
    db.session.delete(pub)
    db.session.commit()
    log_action('researcher_publication_delete', f'Deleted: {title}', current_user.id)
    flash('Article deleted.', 'success')
    return redirect(url_for('researcher.publications_list'))


# ─── Performance Alerts ──────────────────────────────────────────────────────

@researcher_bp.route('/alerts')
@login_required
@researcher_required
def alerts_list():
    """View performance change alerts for all participants."""
    severity_filter = request.args.get('severity', '')
    query = Alert.query.order_by(desc(Alert.created_at))
    if severity_filter:
        query = query.filter_by(severity=severity_filter)
    alerts, page, total, total_pages = _paginate(query)
    return render_template(
        'researcher/alerts/list.html',
        alerts=alerts, page=page, total=total,
        total_pages=total_pages, severity_filter=severity_filter,
    )


@researcher_bp.route('/alerts/<int:alert_id>/read', methods=['POST'])
@login_required
@researcher_required
def alerts_mark_read(alert_id):
    """Mark a performance alert as reviewed."""
    alert = Alert.query.get_or_404(alert_id)
    alert.is_read = True
    db.session.commit()
    return redirect(url_for('researcher.alerts_list'))


# ─── Analytics Reports ───────────────────────────────────────────────────────

@researcher_bp.route('/analytics')
@login_required
@researcher_required
def analytics_dashboard():
    """Cohort analytics and saved reports."""
    cohort = generate_cohort_analytics()
    reports = AnalyticsReport.query.filter_by(
        researcher_id=current_user.id,
    ).order_by(desc(AnalyticsReport.generated_at)).limit(10).all()
    return render_template(
        'researcher/analytics/dashboard.html',
        cohort=cohort,
        reports=reports,
    )


@researcher_bp.route('/analytics/generate', methods=['POST'])
@login_required
@researcher_required
def analytics_generate():
    """Generate and save a cohort analytics report."""
    cohort = generate_cohort_analytics()
    title = request.form.get('title', '').strip() or 'Cohort Performance Summary'
    content = (
        f"Participants: {cohort['total_participants']}\n"
        f"With assessment data: {cohort['participants_with_data']}\n"
        f"Total cycles completed: {cohort['total_cycles_completed']}\n"
        f"Average latest cognitive score: {cohort['avg_latest_score']}\n"
        f"Total performance alerts: {cohort['total_alerts']}\n"
        f"Unread alerts: {cohort['unread_alerts']}\n"
    )
    report = AnalyticsReport(
        researcher_id=current_user.id,
        report_type='cohort_summary',
        title=title,
        content=content,
    )
    db.session.add(report)
    db.session.commit()
    log_action('analytics_report', f'Generated: {title}', current_user.id)
    flash('Analytics report generated.', 'success')
    return redirect(url_for('researcher.analytics_dashboard'))

