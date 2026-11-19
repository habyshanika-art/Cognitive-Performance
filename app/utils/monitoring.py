"""
Continuous Cognitive Monitoring
-------------------------------
Cycle-based tracking with personal baselines, per-metric deviation scores,
and alerts only when declines persist across consecutive post-baseline cycles.
"""

from decimal import Decimal
from statistics import mean, pstdev

from sqlalchemy import func

from app import db
from app.models.task import Task
from app.models.cognitive_metrics import CognitiveMetrics
from app.models.aggregated_metrics import AggregatedMetrics
from app.models.alert import Alert
from app.models.notification import Notification
from app.models.user import User
from app.utils.helpers import get_system_setting


TASK_TYPES = ['typing', 'reaction', 'memory', 'concentration']

# First N completed cycles form the personal baseline (no alerts during baseline)
BASELINE_CYCLES = 3
# Alert only when this many consecutive post-baseline cycles are flagged
PERSISTENCE_CYCLES = 2

# Percent deviation from baseline mean to flag a single cycle
TYPING_DROP_PERCENT = 15
REACTION_INCREASE_PERCENT = 20
MEMORY_DROP_PERCENT = 15
CONCENTRATION_DROP_PERCENT = 15
OVERALL_DROP_POINTS = 12


def get_assessments_per_cycle():
    """Read attempts-per-cycle from admin settings (default 5)."""
    try:
        return max(1, int(get_system_setting('assessments_per_cycle', '5')))
    except (TypeError, ValueError):
        return 5


def get_baseline_cycle_count():
    try:
        return max(1, int(get_system_setting('baseline_cycles', str(BASELINE_CYCLES))))
    except (TypeError, ValueError):
        return BASELINE_CYCLES


def get_persistence_cycle_count():
    try:
        return max(1, int(get_system_setting('persistence_cycles', str(PERSISTENCE_CYCLES))))
    except (TypeError, ValueError):
        return PERSISTENCE_CYCLES


def _valid_task_filter(query):
    """Only count completed, valid, non-practice attempts toward cycles."""
    return query.filter(
        Task.status == 'completed',
        Task.is_valid.is_(True),
        Task.is_practice.is_(False),
    )


def get_completed_cycle_count(user_id):
    """Number of fully completed and aggregated assessment cycles."""
    return AggregatedMetrics.query.filter_by(user_id=user_id).count()


def get_current_cycle(user_id):
    """Active assessment cycle (1-based). Increments after each aggregated cycle."""
    return get_completed_cycle_count(user_id) + 1


def get_attempt_count(user_id, task_type, cycle_number=None):
    """Count valid completed non-practice attempts for a task type within a cycle."""
    if cycle_number is None:
        cycle_number = get_current_cycle(user_id)
    q = Task.query.filter_by(
        user_id=user_id,
        task_type=task_type,
        cycle_number=cycle_number,
    )
    return _valid_task_filter(q).count()


def can_attempt_assessment(user_id, task_type, max_attempts=None, practice=False):
    """Return True if user has remaining attempts (practice always allowed)."""
    if practice:
        return True
    if max_attempts is None:
        max_attempts = get_assessments_per_cycle()
    return get_attempt_count(user_id, task_type) < max_attempts


def get_next_attempt_number(user_id, task_type):
    """Next attempt number within the current cycle (1-based), valid attempts only."""
    return get_attempt_count(user_id, task_type) + 1


def is_cycle_complete(user_id, cycle_number=None):
    """True when all task types have required valid attempts in the cycle."""
    if cycle_number is None:
        cycle_number = get_current_cycle(user_id)
    required = get_assessments_per_cycle()
    return all(
        get_attempt_count(user_id, tt, cycle_number) >= required
        for tt in TASK_TYPES
    )


def _cycle_metric_avg(user_id, task_type, cycle_number, column):
    return db.session.query(func.avg(column)).filter(
        CognitiveMetrics.user_id == user_id,
        CognitiveMetrics.task_type == task_type,
        CognitiveMetrics.cycle_number == cycle_number,
        CognitiveMetrics.task_id.in_(
            db.session.query(Task.id).filter(
                Task.user_id == user_id,
                Task.task_type == task_type,
                Task.cycle_number == cycle_number,
                Task.status == 'completed',
                Task.is_valid.is_(True),
                Task.is_practice.is_(False),
            )
        ),
    ).scalar()


def _compute_overall_score(avg_typing, avg_reaction, avg_memory=None, avg_concentration=None):
    """Combine typing, reaction, memory, and concentration into a 0–100 score."""
    scores = []
    if avg_typing is not None:
        scores.append(min(float(avg_typing), 100))
    if avg_reaction is not None:
        scores.append(max(0, 100 - (float(avg_reaction) / 10)))
    if avg_memory is not None:
        scores.append(min(float(avg_memory), 100))
    if avg_concentration is not None:
        scores.append(min(float(avg_concentration), 100))
    return round(sum(scores) / len(scores), 2) if scores else 0


def get_cycle_averages(user_id, cycle_number):
    """Calculate averages for a specific cycle from cognitive_metrics."""
    avg_typing = _cycle_metric_avg(
        user_id, 'typing', cycle_number, CognitiveMetrics.typing_speed_wpm
    )
    avg_reaction = _cycle_metric_avg(
        user_id, 'reaction', cycle_number, CognitiveMetrics.response_time_ms
    )
    avg_memory = _cycle_metric_avg(
        user_id, 'memory', cycle_number, CognitiveMetrics.memory_score
    )
    avg_concentration = _cycle_metric_avg(
        user_id, 'concentration', cycle_number, CognitiveMetrics.concentration_score
    )
    return {
        'avg_typing_speed': round(float(avg_typing), 2) if avg_typing is not None else None,
        'avg_reaction_time': round(float(avg_reaction), 2) if avg_reaction is not None else None,
        'avg_memory_score': round(float(avg_memory), 2) if avg_memory is not None else None,
        'avg_concentration_score': (
            round(float(avg_concentration), 2) if avg_concentration is not None else None
        ),
        'overall_cognitive_score': _compute_overall_score(
            avg_typing, avg_reaction, avg_memory, avg_concentration
        ),
    }


def get_user_averages(user_id, cycle_number=None):
    """Running averages for the current (or specified) cycle — no lifetime fallback."""
    if cycle_number is None:
        cycle_number = get_current_cycle(user_id)

    cycle_avgs = get_cycle_averages(user_id, cycle_number)
    has_data = any(
        cycle_avgs[k] is not None
        for k in (
            'avg_typing_speed', 'avg_reaction_time',
            'avg_memory_score', 'avg_concentration_score',
        )
    )
    if not has_data:
        # Prefer last completed aggregated cycle over misleading lifetime averages
        last = (
            AggregatedMetrics.query.filter_by(user_id=user_id)
            .order_by(AggregatedMetrics.cycle_number.desc())
            .first()
        )
        if last:
            return {
                'avg_typing_speed': (
                    float(last.avg_typing_speed) if last.avg_typing_speed is not None else None
                ),
                'avg_reaction_time': (
                    float(last.avg_response_time) if last.avg_response_time is not None else None
                ),
                'avg_memory_score': (
                    float(last.avg_memory_score) if last.avg_memory_score is not None else None
                ),
                'avg_concentration_score': (
                    float(last.avg_concentration_score)
                    if getattr(last, 'avg_concentration_score', None) is not None else None
                ),
                'overall_cognitive_score': (
                    float(last.overall_cognitive_score)
                    if last.overall_cognitive_score is not None else 0
                ),
                'cycle_number': last.cycle_number,
                'typing_attempts': get_attempt_count(user_id, 'typing', last.cycle_number),
                'reaction_attempts': get_attempt_count(user_id, 'reaction', last.cycle_number),
                'memory_attempts': get_attempt_count(user_id, 'memory', last.cycle_number),
                'concentration_attempts': get_attempt_count(
                    user_id, 'concentration', last.cycle_number
                ),
            }

    return {
        **cycle_avgs,
        'cycle_number': cycle_number,
        'typing_attempts': get_attempt_count(user_id, 'typing', cycle_number),
        'reaction_attempts': get_attempt_count(user_id, 'reaction', cycle_number),
        'memory_attempts': get_attempt_count(user_id, 'memory', cycle_number),
        'concentration_attempts': get_attempt_count(user_id, 'concentration', cycle_number),
    }


def get_typing_progress(user_id, cycle_number=None):
    if cycle_number is None:
        cycle_number = get_current_cycle(user_id)
    metrics = CognitiveMetrics.query.filter_by(
        user_id=user_id, task_type='typing', cycle_number=cycle_number,
    ).order_by(CognitiveMetrics.attempt_number).all()
    return {
        'labels': [f'Attempt {m.attempt_number}' for m in metrics],
        'values': [float(m.typing_speed_wpm or 0) for m in metrics],
        'cycle_number': cycle_number,
    }


def get_reaction_progress(user_id, cycle_number=None):
    if cycle_number is None:
        cycle_number = get_current_cycle(user_id)
    metrics = CognitiveMetrics.query.filter_by(
        user_id=user_id, task_type='reaction', cycle_number=cycle_number,
    ).order_by(CognitiveMetrics.attempt_number).all()
    return {
        'labels': [f'Attempt {m.attempt_number}' for m in metrics],
        'values': [int(m.response_time_ms or 0) for m in metrics],
        'cycle_number': cycle_number,
    }


def get_memory_progress(user_id, cycle_number=None):
    if cycle_number is None:
        cycle_number = get_current_cycle(user_id)
    metrics = CognitiveMetrics.query.filter_by(
        user_id=user_id, task_type='memory', cycle_number=cycle_number,
    ).order_by(CognitiveMetrics.attempt_number).all()
    return {
        'labels': [f'Attempt {m.attempt_number}' for m in metrics],
        'values': [float(m.memory_score or 0) for m in metrics],
        'cycle_number': cycle_number,
    }


def get_concentration_progress(user_id, cycle_number=None):
    if cycle_number is None:
        cycle_number = get_current_cycle(user_id)
    metrics = CognitiveMetrics.query.filter_by(
        user_id=user_id, task_type='concentration', cycle_number=cycle_number,
    ).order_by(CognitiveMetrics.attempt_number).all()
    return {
        'labels': [f'Attempt {m.attempt_number}' for m in metrics],
        'values': [float(m.concentration_score or 0) for m in metrics],
        'cycle_number': cycle_number,
    }


def get_baseline_stats(user_id):
    """
    Mean (± band) from the first baseline cycles.
    Returns None fields until enough baseline cycles exist.
    """
    n = get_baseline_cycle_count()
    cycles = (
        AggregatedMetrics.query.filter_by(user_id=user_id)
        .order_by(AggregatedMetrics.cycle_number)
        .limit(n)
        .all()
    )
    if len(cycles) < n:
        return {
            'ready': False,
            'baseline_cycles': len(cycles),
            'required': n,
            'typing_mean': None,
            'typing_std': None,
            'reaction_mean': None,
            'reaction_std': None,
            'memory_mean': None,
            'memory_std': None,
            'concentration_mean': None,
            'concentration_std': None,
            'overall_mean': None,
            'overall_std': None,
            'typing_low': None,
            'typing_high': None,
            'reaction_low': None,
            'reaction_high': None,
            'overall_low': None,
            'overall_high': None,
        }

    typing_vals = [float(c.avg_typing_speed) for c in cycles if c.avg_typing_speed]
    reaction_vals = [float(c.avg_response_time) for c in cycles if c.avg_response_time]
    memory_vals = [float(c.avg_memory_score) for c in cycles if c.avg_memory_score]
    concentration_vals = [
        float(c.avg_concentration_score) for c in cycles if c.avg_concentration_score
    ]
    overall_vals = [float(c.overall_cognitive_score or 0) for c in cycles]

    def _stats(vals):
        if not vals:
            return None, None, None, None
        m = mean(vals)
        s = pstdev(vals) if len(vals) > 1 else m * 0.1
        # Band: mean ± max(std, 10% of mean) for chart shading
        pad = max(s, abs(m) * 0.1) if m else s
        return round(m, 2), round(s, 2), round(m - pad, 2), round(m + pad, 2)

    t_m, t_s, t_lo, t_hi = _stats(typing_vals)
    r_m, r_s, r_lo, r_hi = _stats(reaction_vals)
    mem_m, mem_s, _, _ = _stats(memory_vals)
    conc_m, conc_s, _, _ = _stats(concentration_vals)
    o_m, o_s, o_lo, o_hi = _stats(overall_vals)

    return {
        'ready': True,
        'baseline_cycles': n,
        'required': n,
        'typing_mean': t_m,
        'typing_std': t_s,
        'reaction_mean': r_m,
        'reaction_std': r_s,
        'memory_mean': mem_m,
        'memory_std': mem_s,
        'concentration_mean': conc_m,
        'concentration_std': conc_s,
        'overall_mean': o_m,
        'overall_std': o_s,
        'typing_low': t_lo,
        'typing_high': t_hi,
        'reaction_low': r_lo,
        'reaction_high': r_hi,
        'overall_low': o_lo,
        'overall_high': o_hi,
    }


def _percent_deviation(current, baseline, higher_is_worse=False):
    """Percent change from baseline. Positive = worse performance."""
    if baseline is None or baseline == 0 or current is None:
        return None
    if higher_is_worse:
        return round((current - baseline) / abs(baseline) * 100, 2)
    return round((baseline - current) / abs(baseline) * 100, 2)


def compute_cycle_deviations(user_id, cycle_number, avgs, baseline):
    """Per-metric deviation scores vs baseline (positive = decline)."""
    if not baseline.get('ready') or cycle_number <= get_baseline_cycle_count():
        return {
            'typing_deviation': None,
            'reaction_deviation': None,
            'memory_deviation': None,
            'concentration_deviation': None,
            'overall_deviation': None,
            'is_flagged_cycle': False,
            'flag_reasons': [],
        }

    typing_dev = _percent_deviation(
        avgs.get('avg_typing_speed'), baseline.get('typing_mean'), False
    )
    reaction_dev = _percent_deviation(
        avgs.get('avg_reaction_time'), baseline.get('reaction_mean'), True
    )
    memory_dev = _percent_deviation(
        avgs.get('avg_memory_score'), baseline.get('memory_mean'), False
    )
    concentration_dev = _percent_deviation(
        avgs.get('avg_concentration_score'), baseline.get('concentration_mean'), False
    )
    overall_dev = None
    if baseline.get('overall_mean') and avgs.get('overall_cognitive_score') is not None:
        overall_dev = round(
            baseline['overall_mean'] - float(avgs['overall_cognitive_score']), 2
        )

    reasons = []
    flagged = False
    if typing_dev is not None and typing_dev >= TYPING_DROP_PERCENT:
        reasons.append(f'typing ↓{typing_dev:.1f}% vs baseline')
        flagged = True
    if reaction_dev is not None and reaction_dev >= REACTION_INCREASE_PERCENT:
        reasons.append(f'reaction ↑{reaction_dev:.1f}% vs baseline')
        flagged = True
    if memory_dev is not None and memory_dev >= MEMORY_DROP_PERCENT:
        reasons.append(f'memory ↓{memory_dev:.1f}% vs baseline')
        flagged = True
    if concentration_dev is not None and concentration_dev >= CONCENTRATION_DROP_PERCENT:
        reasons.append(f'concentration ↓{concentration_dev:.1f}% vs baseline')
        flagged = True
    if overall_dev is not None and overall_dev >= OVERALL_DROP_POINTS:
        reasons.append(f'overall −{overall_dev:.1f} pts vs baseline')
        flagged = True

    return {
        'typing_deviation': typing_dev,
        'reaction_deviation': reaction_dev,
        'memory_deviation': memory_dev,
        'concentration_deviation': concentration_dev,
        'overall_deviation': overall_dev,
        'is_flagged_cycle': flagged,
        'flag_reasons': reasons,
    }


def get_cycle_trend_chart(user_id):
    """Longitudinal chart with baseline band and flagged cycle markers."""
    cycles = AggregatedMetrics.query.filter_by(
        user_id=user_id,
    ).order_by(AggregatedMetrics.cycle_number).all()
    baseline = get_baseline_stats(user_id)
    n_base = get_baseline_cycle_count()

    return {
        'labels': [f'Cycle {c.cycle_number}' for c in cycles],
        'overall_scores': [float(c.overall_cognitive_score or 0) for c in cycles],
        'typing_speeds': [float(c.avg_typing_speed or 0) for c in cycles],
        'reaction_times': [float(c.avg_response_time or 0) for c in cycles],
        'memory_scores': [float(c.avg_memory_score or 0) for c in cycles],
        'concentration_scores': [float(c.avg_concentration_score or 0) for c in cycles],
        'flagged': [bool(c.is_flagged) for c in cycles],
        'deviations': [float(c.overall_deviation) if c.overall_deviation is not None else None
                       for c in cycles],
        'baseline': {
            'ready': baseline['ready'],
            'cycles': n_base,
            'overall_mean': baseline['overall_mean'],
            'overall_low': baseline['overall_low'],
            'overall_high': baseline['overall_high'],
            'typing_mean': baseline['typing_mean'],
            'typing_low': baseline['typing_low'],
            'typing_high': baseline['typing_high'],
            'reaction_mean': baseline['reaction_mean'],
            'reaction_low': baseline['reaction_low'],
            'reaction_high': baseline['reaction_high'],
        },
    }


def get_monitoring_status(user_id):
    """Summary for dashboards: cycle progress, baseline, trend, alerts."""
    cycle = get_current_cycle(user_id)
    required = get_assessments_per_cycle()
    typing_done = get_attempt_count(user_id, 'typing', cycle)
    reaction_done = get_attempt_count(user_id, 'reaction', cycle)
    memory_done = get_attempt_count(user_id, 'memory', cycle)
    concentration_done = get_attempt_count(user_id, 'concentration', cycle)
    total_required = required * len(TASK_TYPES)
    total_done = typing_done + reaction_done + memory_done + concentration_done

    cycles = AggregatedMetrics.query.filter_by(
        user_id=user_id,
    ).order_by(AggregatedMetrics.cycle_number).all()
    baseline = get_baseline_stats(user_id)
    n_base = get_baseline_cycle_count()

    trend = 'stable'
    trend_detail = (
        f'Complete {n_base} assessment cycles to establish your personal baseline.'
        if not baseline['ready']
        else 'Performance is within your baseline range.'
    )

    if baseline['ready'] and cycles:
        latest = cycles[-1]
        if latest.is_flagged:
            trend = 'declining'
            trend_detail = (
                f'Cycle {latest.cycle_number} is outside your baseline. '
                'Alerts fire only if this persists across consecutive cycles.'
            )
        elif latest.overall_deviation is not None and float(latest.overall_deviation) <= -5:
            trend = 'improving'
            trend_detail = 'Recent overall score is above your personal baseline.'
        elif len(cycles) >= 2:
            prev = float(cycles[-2].overall_cognitive_score or 0)
            curr = float(cycles[-1].overall_cognitive_score or 0)
            diff = curr - prev
            if diff >= 5:
                trend = 'improving'
                trend_detail = f'Overall score improved by {diff:.1f} points since last cycle.'
            elif diff <= -5:
                trend = 'declining'
                trend_detail = f'Overall score dropped by {abs(diff):.1f} points since last cycle.'

    user_alerts = Alert.query.filter_by(user_id=user_id).count()

    return {
        'current_cycle': cycle,
        'completed_cycles': len(cycles),
        'attempts_per_cycle': required,
        'typing_done': typing_done,
        'reaction_done': reaction_done,
        'memory_done': memory_done,
        'concentration_done': concentration_done,
        'total_done': total_done,
        'total_required': total_required,
        'cycle_progress_pct': round(total_done / total_required * 100) if total_required else 0,
        'cycle_complete': is_cycle_complete(user_id, cycle),
        'trend': trend,
        'trend_detail': trend_detail,
        'alert_count': user_alerts,
        'baseline_ready': baseline['ready'],
        'baseline_cycles_done': min(len(cycles), n_base),
        'baseline_cycles_required': n_base,
        'baseline': baseline,
    }


def _create_alert(user_id, alert_type, message, severity='medium'):
    alert = Alert(
        user_id=user_id,
        alert_type=alert_type,
        message=message,
        severity=severity,
    )
    db.session.add(alert)
    return alert


def _notify_user_performance_change(user, title, message):
    if not getattr(user, 'notify_performance_alerts', True):
        return
    notif = Notification(
        user_id=user.id,
        notification_type='performance_alert',
        title=title,
        message=message,
        link_url='/user/results',
    )
    db.session.add(notif)
    try:
        from app.utils.email_service import send_user_email
        body = (
            f'Hello {user.first_name},\n\n'
            f'{message}\n\n'
            f'This is an automated monitoring notice, not a medical diagnosis.\n'
            f'— CogMonitor'
        )
        send_user_email(
            user, title, body, category='alert',
            also_notify=False, link_url='/user/results', commit=False,
        )
    except Exception:
        pass


def detect_persistent_deviations(user_id, current_cycle):
    """
    Alert only when flagged deviations persist for PERSISTENCE_CYCLES
    consecutive post-baseline cycles. Single-cycle drops do not alert.
    """
    n_base = get_baseline_cycle_count()
    persist_n = get_persistence_cycle_count()

    if current_cycle <= n_base:
        return []

    # Need persist_n consecutive flagged cycles ending at current_cycle
    recent = (
        AggregatedMetrics.query.filter(
            AggregatedMetrics.user_id == user_id,
            AggregatedMetrics.cycle_number > n_base,
            AggregatedMetrics.cycle_number <= current_cycle,
        )
        .order_by(AggregatedMetrics.cycle_number.desc())
        .limit(persist_n)
        .all()
    )
    if len(recent) < persist_n:
        return []
    if not all(c.is_flagged for c in recent):
        return []

    user = User.query.get(user_id)
    cycle_nums = sorted(c.cycle_number for c in recent)
    window_label = f'across cycles {cycle_nums[0]}–{cycle_nums[-1]}'

    # Avoid duplicate alerts for the same window (match actual message text)
    existing = Alert.query.filter(
        Alert.user_id == user_id,
        Alert.alert_type == 'persistent_deviation',
        Alert.message.contains(window_label),
    ).first()
    if existing:
        return []

    reasons = []
    for c in recent:
        if c.typing_deviation and float(c.typing_deviation) >= TYPING_DROP_PERCENT:
            reasons.append(f'Cycle {c.cycle_number}: typing ↓{float(c.typing_deviation):.1f}%')
        if c.reaction_deviation and float(c.reaction_deviation) >= REACTION_INCREASE_PERCENT:
            reasons.append(f'Cycle {c.cycle_number}: reaction ↑{float(c.reaction_deviation):.1f}%')
        if c.memory_deviation and float(c.memory_deviation) >= MEMORY_DROP_PERCENT:
            reasons.append(f'Cycle {c.cycle_number}: memory ↓{float(c.memory_deviation):.1f}%')
        if getattr(c, 'concentration_deviation', None) and float(c.concentration_deviation) >= CONCENTRATION_DROP_PERCENT:
            reasons.append(
                f'Cycle {c.cycle_number}: concentration ↓{float(c.concentration_deviation):.1f}%'
            )

    msg = (
        f'Persistent performance deviation {window_label} (vs personal baseline). '
        + ('; '.join(reasons[:6]) if reasons else 'Multiple metrics outside baseline band.')
        + ' This is a monitoring signal only — not a medical diagnosis.'
    )
    alert = _create_alert(user_id, 'persistent_deviation', msg, 'high')

    if user:
        summary = (
            f'We detected persistent changes across {persist_n} consecutive cycles '
            f'compared with your baseline (cycles 1–{n_base}). '
            'This is not a diagnosis — please review your results and rest if needed.'
        )
        _notify_user_performance_change(
            user, 'Persistent Performance Change Detected', summary,
        )

    return [alert]


def finalize_cycle_if_complete(user_id):
    """
    When a cycle is complete, store aggregated metrics, deviations,
    and run persistent-deviation detection (not single-drop alerts).
    """
    cycle = get_current_cycle(user_id)
    if not is_cycle_complete(user_id, cycle):
        return None

    existing = AggregatedMetrics.query.filter_by(
        user_id=user_id, cycle_number=cycle,
    ).first()
    if existing:
        return existing

    avgs = get_cycle_averages(user_id, cycle)
    baseline = get_baseline_stats(user_id)
    # Baseline stats before this cycle is saved: if cycle <= N, still baseline
    n_base = get_baseline_cycle_count()
    is_baseline = cycle <= n_base

    # For deviation, use baseline from prior cycles only
    if cycle > n_base:
        deviations = compute_cycle_deviations(user_id, cycle, avgs, baseline)
    else:
        deviations = {
            'typing_deviation': None,
            'reaction_deviation': None,
            'memory_deviation': None,
            'concentration_deviation': None,
            'overall_deviation': None,
            'is_flagged_cycle': False,
            'flag_reasons': [],
        }

    aggregated = AggregatedMetrics(
        user_id=user_id,
        avg_typing_speed=avgs['avg_typing_speed'],
        avg_response_time=avgs['avg_reaction_time'],
        avg_memory_score=avgs['avg_memory_score'],
        avg_concentration_score=avgs['avg_concentration_score'],
        overall_cognitive_score=Decimal(str(avgs['overall_cognitive_score'])),
        cycle_number=cycle,
        typing_deviation=deviations['typing_deviation'],
        reaction_deviation=deviations['reaction_deviation'],
        memory_deviation=deviations['memory_deviation'],
        concentration_deviation=deviations.get('concentration_deviation'),
        overall_deviation=deviations['overall_deviation'],
        is_baseline_cycle=is_baseline,
        is_flagged=deviations['is_flagged_cycle'],
    )
    db.session.add(aggregated)
    db.session.flush()

    detect_persistent_deviations(user_id, cycle)

    user = User.query.get(user_id)
    if user and getattr(user, 'notify_assessment_reminders', True):
        if is_baseline:
            msg = (
                f'You finished baseline cycle {cycle} of {n_base}. '
                f'Overall score: {avgs["overall_cognitive_score"]}.'
            )
        else:
            flag_note = (
                ' This cycle is outside your baseline band (alerts need consecutive flags).'
                if deviations['is_flagged_cycle'] else ''
            )
            msg = (
                f'You finished assessment cycle {cycle}. '
                f'Overall score: {avgs["overall_cognitive_score"]}.{flag_note}'
            )
        notif = Notification(
            user_id=user_id,
            notification_type='cycle_complete',
            title=f'Cycle {cycle} Complete',
            message=msg,
            link_url='/user/assessments',
        )
        db.session.add(notif)
        try:
            from app.utils.email_service import send_user_email
            send_user_email(
                user, f'Cycle {cycle} Complete', msg,
                category='notification', also_notify=False,
                link_url='/user/results', commit=False,
            )
        except Exception:
            pass

    db.session.commit()
    return aggregated


def backfill_aggregated_cycles():
    """Aggregate completed cycles for users who finished before cycle tracking."""
    from app.models.role import Role

    users = User.query.join(Role).filter(Role.name == 'user').all()
    for user in users:
        user.ensure_anonymised_id()
        cycle = 1
        while is_cycle_complete(user.id, cycle):
            existing = AggregatedMetrics.query.filter_by(
                user_id=user.id, cycle_number=cycle,
            ).first()
            if not existing:
                avgs = get_cycle_averages(user.id, cycle)
                n_base = get_baseline_cycle_count()
                baseline = get_baseline_stats(user.id)
                if cycle > n_base and baseline.get('ready'):
                    deviations = compute_cycle_deviations(user.id, cycle, avgs, baseline)
                else:
                    deviations = {
                        'typing_deviation': None, 'reaction_deviation': None,
                        'memory_deviation': None, 'concentration_deviation': None,
                        'overall_deviation': None, 'is_flagged_cycle': False,
                    }
                aggregated = AggregatedMetrics(
                    user_id=user.id,
                    avg_typing_speed=avgs['avg_typing_speed'],
                    avg_response_time=avgs['avg_reaction_time'],
                    avg_memory_score=avgs['avg_memory_score'],
                    avg_concentration_score=avgs['avg_concentration_score'],
                    overall_cognitive_score=Decimal(str(avgs['overall_cognitive_score'])),
                    cycle_number=cycle,
                    typing_deviation=deviations.get('typing_deviation'),
                    reaction_deviation=deviations.get('reaction_deviation'),
                    memory_deviation=deviations.get('memory_deviation'),
                    concentration_deviation=deviations.get('concentration_deviation'),
                    overall_deviation=deviations.get('overall_deviation'),
                    is_baseline_cycle=cycle <= n_base,
                    is_flagged=deviations.get('is_flagged_cycle', False),
                )
                db.session.add(aggregated)
                db.session.flush()
            cycle += 1
    db.session.commit()


def generate_cohort_analytics():
    """Build a summary report from all participants' aggregated metrics."""
    from app.models.role import Role

    participants = User.query.join(Role).filter(
        Role.name == 'user',
        User.data_withdrawn.is_(False),
    ).all()
    total = len(participants)
    with_data = 0
    total_cycles = 0
    alert_count = Alert.query.count()
    avg_scores = []
    flagged_cycles = 0

    for p in participants:
        cycles = AggregatedMetrics.query.filter_by(user_id=p.id).all()
        if cycles:
            with_data += 1
            total_cycles += len(cycles)
            flagged_cycles += sum(1 for c in cycles if c.is_flagged)
            latest = max(cycles, key=lambda c: c.cycle_number)
            avg_scores.append(float(latest.overall_cognitive_score or 0))

    return {
        'total_participants': total,
        'participants_with_data': with_data,
        'total_cycles_completed': total_cycles,
        'flagged_cycles': flagged_cycles,
        'total_alerts': alert_count,
        'avg_latest_score': round(sum(avg_scores) / len(avg_scores), 2) if avg_scores else 0,
        'unread_alerts': Alert.query.filter_by(is_read=False).count(),
    }


def build_participant_export_rows(user_id):
    """Rows for CSV/PDF export of a participant's cycle history."""
    user = User.query.get(user_id)
    cycles = AggregatedMetrics.query.filter_by(
        user_id=user_id,
    ).order_by(AggregatedMetrics.cycle_number).all()
    rows = []
    for c in cycles:
        rows.append({
            'participant_id': user.display_id if user else user_id,
            'cycle': c.cycle_number,
            'avg_typing_wpm': float(c.avg_typing_speed) if c.avg_typing_speed is not None else '',
            'avg_reaction_ms': float(c.avg_response_time) if c.avg_response_time is not None else '',
            'avg_memory_score': float(c.avg_memory_score) if c.avg_memory_score is not None else '',
            'avg_concentration_score': float(c.avg_concentration_score) if c.avg_concentration_score is not None else '',
            'overall_score': float(c.overall_cognitive_score or 0),
            'typing_deviation': float(c.typing_deviation) if c.typing_deviation is not None else '',
            'reaction_deviation': float(c.reaction_deviation) if c.reaction_deviation is not None else '',
            'memory_deviation': float(c.memory_deviation) if c.memory_deviation is not None else '',
            'concentration_deviation': float(c.concentration_deviation) if getattr(c, 'concentration_deviation', None) is not None else '',
            'overall_deviation': float(c.overall_deviation) if c.overall_deviation is not None else '',
            'is_baseline': 'yes' if c.is_baseline_cycle else 'no',
            'is_flagged': 'yes' if c.is_flagged else 'no',
            'calculated_at': c.calculated_at.isoformat() if c.calculated_at else '',
        })
    return rows
