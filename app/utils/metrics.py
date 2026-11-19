"""
Metrics Calculation Utilities
-----------------------------
Feedback interpretation and re-exports from continuous monitoring module.
"""

from app.utils.monitoring import (  # noqa: F401
    get_attempt_count,
    can_attempt_assessment,
    get_next_attempt_number,
    get_typing_progress,
    get_reaction_progress,
    get_memory_progress,
    get_concentration_progress,
    get_user_averages,
    get_assessments_per_cycle,
    get_current_cycle,
    get_cycle_trend_chart,
    get_monitoring_status,
    finalize_cycle_if_complete,
    get_baseline_stats,
    build_participant_export_rows,
)


def _build_metric_feedback(level, label, headline, message, tips):
    """Build a consistent feedback dict for one metric."""
    return {
        'level': level,
        'label': label,
        'headline': headline,
        'message': message,
        'tips': tips,
    }


def _typing_feedback(wpm):
    """Interpret typing speed (WPM) and return guidance."""
    if wpm >= 45:
        return _build_metric_feedback(
            'good', 'Good',
            'Your typing speed is strong',
            f'At {wpm:.1f} WPM you are above the typical young adult range (35–45 WPM). '
            'This suggests good motor coordination and sustained attention.',
            [
                'Keep practising regularly to maintain your speed and accuracy.',
                'Take short breaks during long study or screen sessions.',
                'Stay hydrated and get enough sleep to protect focus.',
            ],
        )
    if wpm >= 28:
        return _build_metric_feedback(
            'average', 'Average',
            'Your typing speed is in the average range',
            f'At {wpm:.1f} WPM you are within a typical range, but there is room to improve.',
            [
                'Practise touch typing for 10–15 minutes a day.',
                'Focus on accuracy first, then gradually increase speed.',
                'Reduce distractions and take breaks to prevent mental fatigue.',
                'Repeat assessments weekly to track improvement.',
            ],
        )
    return _build_metric_feedback(
        'needs_improvement', 'Needs Improvement',
        'Your typing speed could improve',
        f'At {wpm:.1f} WPM your result is below the typical range. '
        'This may reflect fatigue, distraction, or limited typing practice.',
        [
            'Use free online typing tutors to build muscle memory.',
            'Practise in a quiet environment with good posture.',
            'Get 7–9 hours of sleep before taking assessments.',
            'Take the typing test again after a few days of practice.',
            'If results stay low, consider requesting researcher feedback.',
        ],
    )


def _reaction_feedback(ms):
    """Interpret reaction time (ms) and return guidance. Lower is better."""
    if ms <= 400:
        return _build_metric_feedback(
            'good', 'Good',
            'Your reaction time is strong',
            f'At {int(ms)} ms you are responding quickly for a web-based click test '
            '(good range: under 400 ms).',
            [
                'Maintain regular sleep and physical activity.',
                'Limit caffeine crashes before assessments.',
                'Continue periodic tests to monitor any changes over time.',
            ],
        )
    if ms <= 600:
        return _build_metric_feedback(
            'average', 'Average',
            'Your reaction time is average',
            f'At {int(ms)} ms you are in a normal web-test range (about 400–600 ms). '
            'Faster responses are still possible with practice and focus.',
            [
                'Stay alert — avoid testing when tired or hungry.',
                'Minimise background noise and phone notifications.',
                'Do light exercise to support alertness and blood flow.',
                'Practise the reaction test to improve focus.',
            ],
        )
    return _build_metric_feedback(
        'needs_improvement', 'Needs Improvement',
        'Your reaction time is slower than expected',
        f'At {int(ms)} ms your response is slower than the expected web-test range '
        '(good under 400 ms, average up to 600 ms). '
        'Fatigue, stress, or distraction often affect this score.',
        [
            'Take assessments when you are well-rested and focused.',
            'Reduce screen time before testing to avoid mental fatigue.',
            'Try deep breathing for 1 minute before starting the test.',
            'Stay hydrated and eat balanced meals for steady energy.',
            'Retest the test on a different day and compare results.',
        ],
    )


def _memory_feedback(score):
    """Interpret short-term memory digit-span score (0–100)."""
    if score >= 70:
        return _build_metric_feedback(
            'good', 'Good',
            'Your short-term memory score is strong',
            f'At {score:.0f}/100 you recalled sequences accurately under time pressure.',
            [
                'Sleep supports memory consolidation — aim for 7–9 hours.',
                'Repeat the memory task across cycles to build your baseline.',
            ],
        )
    if score >= 45:
        return _build_metric_feedback(
            'average', 'Average',
            'Your memory score is in the average range',
            f'At {score:.0f}/100 there is room to strengthen working memory.',
            [
                'Reduce distractions before testing.',
                'Use chunking (group digits) when practising sequences.',
                'Retake after rest — fatigue lowers working-memory scores.',
            ],
        )
    return _build_metric_feedback(
        'needs_improvement', 'Needs Improvement',
        'Your memory score suggests limited recall this session',
        f'At {score:.0f}/100 results may reflect fatigue, distraction, or first-time practice.',
        [
            'Try a practice attempt before counting attempts toward your cycle.',
            'Test when alert — avoid late-night sessions.',
        ],
    )


def _concentration_feedback(score):
    """Interpret sustained-attention concentration score (0–100)."""
    if score >= 75:
        return _build_metric_feedback(
            'good', 'Good',
            'Your concentration score is strong',
            f'At {score:.0f}/100 you sustained attention well on the go/no-go task.',
            [
                'Keep short focused work blocks with breaks.',
                'Protect sleep — attention drops quickly with fatigue.',
            ],
        )
    if score >= 50:
        return _build_metric_feedback(
            'average', 'Average',
            'Your concentration score is average',
            f'At {score:.0f}/100 attention was mixed — some hits with some false alarms or misses.',
            [
                'Silence notifications before testing.',
                'Practise the concentration task when you feel most alert.',
            ],
        )
    return _build_metric_feedback(
        'needs_improvement', 'Needs Improvement',
        'Your concentration score suggests attention lapses',
        f'At {score:.0f}/100 misses or false clicks were high this session. Not a diagnosis.',
        [
            'Retake after rest; avoid testing when tired or multitasking.',
            'Use practice mode first to learn the target letter.',
        ],
    )


def _overall_feedback(score, typing_level, reaction_level):
    """Summarise overall cognitive performance."""
    if score >= 65:
        return _build_metric_feedback(
            'good', 'Good Overall',
            'Your overall cognitive performance looks healthy',
            f'With a score of {score}, your combined results are strong. '
            'This is monitoring feedback only — not a medical diagnosis.',
            [
                'Keep completing assessments to build a reliable baseline.',
                'Maintain healthy sleep, diet, and exercise habits.',
                'Watch for gradual trends rather than single test scores.',
            ],
        )
    if score >= 40:
        return _build_metric_feedback(
            'average', 'Average Overall',
            'Your overall score is moderate — room to grow',
            f'Your overall score of {score} suggests mixed performance. '
            'This is not a diagnosis.',
            [
                'Improve whichever metric scored lower.',
                'Take assessments at the same time of day for fair comparison.',
                'Manage stress with breaks, walks, and consistent sleep.',
                'Complete all attempts per cycle for more accurate averages.',
            ],
        )
    return _build_metric_feedback(
        'needs_improvement', 'Needs Attention',
        'Your overall score suggests you should focus on improvement',
        f'At {score}, your combined results are below the expected range. '
        'This does not mean something is medically wrong — often it reflects fatigue or practice.',
        [
            'Prioritise sleep (7–9 hours) before your next assessment cycle.',
            'Practise typing, reaction, and memory tests several times.',
            'Reduce distractions and test when you feel most alert.',
            'Use Request Feedback to ask a researcher for personalised advice.',
            'Retest weekly and track whether scores improve over time.',
        ],
    )


def get_results_feedback(averages):
    """
    Generate user-friendly interpretation and tips for the results page.
    """
    feedback = {
        'typing': None,
        'reaction': None,
        'memory': None,
        'concentration': None,
        'overall': None,
        'has_any_data': False,
    }

    if averages.get('avg_typing_speed') is not None:
        feedback['typing'] = _typing_feedback(averages['avg_typing_speed'])
        feedback['has_any_data'] = True

    if averages.get('avg_reaction_time') is not None:
        feedback['reaction'] = _reaction_feedback(averages['avg_reaction_time'])
        feedback['has_any_data'] = True

    if averages.get('avg_memory_score') is not None:
        feedback['memory'] = _memory_feedback(averages['avg_memory_score'])
        feedback['has_any_data'] = True

    if averages.get('avg_concentration_score') is not None:
        feedback['concentration'] = _concentration_feedback(averages['avg_concentration_score'])
        feedback['has_any_data'] = True

    if feedback['has_any_data'] and averages.get('overall_cognitive_score') is not None:
        typing_level = feedback['typing']['level'] if feedback['typing'] else 'average'
        reaction_level = feedback['reaction']['level'] if feedback['reaction'] else 'average'
        feedback['overall'] = _overall_feedback(
            averages['overall_cognitive_score'],
            typing_level,
            reaction_level,
        )

    return feedback
