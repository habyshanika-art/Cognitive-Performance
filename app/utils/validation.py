"""
Assessment Data Validation
--------------------------
Rejects invalid attempts (paste, impossible times, too few keystrokes)
and classifies device type from the User-Agent string.
"""

MIN_TYPING_KEYSTROKES = 20
MIN_TYPING_CHARS = 15
MAX_PLAUSIBLE_WPM = 200
MIN_REACTION_MS = 100
MAX_REACTION_MS = 2500
MIN_MEMORY_SCORE = 0
MAX_MEMORY_SCORE = 100


def detect_device_type(user_agent):
    """Classify device as desktop, mobile, or tablet from User-Agent."""
    ua = (user_agent or '').lower()
    if not ua:
        return 'unknown'
    if 'ipad' in ua or 'tablet' in ua or ('android' in ua and 'mobile' not in ua):
        return 'tablet'
    if any(x in ua for x in ('mobile', 'iphone', 'ipod', 'android', 'webos', 'blackberry')):
        return 'mobile'
    return 'desktop'


def validate_typing_attempt(data):
    """
    Validate typing assessment payload.
    Returns (ok: bool, errors: list[str], cleaned: dict).
    """
    errors = []
    raw = data.get('raw_events') or {}
    chars_typed = int(raw.get('chars_typed') or data.get('chars_typed') or 0)
    keystrokes = int(raw.get('keystroke_count') or chars_typed)
    paste_detected = bool(raw.get('paste_detected'))
    wpm = float(data.get('typing_speed_wpm') or 0)
    time_ms = int(data.get('time_taken_ms') or 0)

    if paste_detected:
        errors.append('Pasted text is not allowed. Please type the passage manually.')
    if keystrokes < MIN_TYPING_KEYSTROKES and chars_typed < MIN_TYPING_CHARS:
        errors.append(
            f'Too few keystrokes ({keystrokes}). Type at least '
            f'{MIN_TYPING_KEYSTROKES} characters of the passage.'
        )
    if wpm > MAX_PLAUSIBLE_WPM:
        errors.append(f'Impossible typing speed ({wpm} WPM). Attempt rejected.')
    if wpm < 1 and chars_typed < MIN_TYPING_CHARS:
        errors.append('Typing speed too low or incomplete attempt.')
    if time_ms > 0 and time_ms < 2000 and chars_typed >= MIN_TYPING_CHARS:
        errors.append('Completion time unrealistically fast for typed text.')

    cleaned = {
        'typing_speed_wpm': wpm,
        'keystroke_count': keystrokes,
        'paste_detected': paste_detected,
    }
    return len(errors) == 0, errors, cleaned


def validate_reaction_attempt(data):
    """
    Validate reaction assessment. Filters impossible trial times.
    Returns (ok, errors, cleaned) where cleaned includes filtered avg.
    """
    errors = []
    raw = data.get('raw_events') or {}
    trials = list(raw.get('trials') or [])
    valid_trials = [
        int(t) for t in trials
        if MIN_REACTION_MS <= int(t) <= MAX_REACTION_MS
    ]
    if len(valid_trials) < 2:
        errors.append(
            f'Need at least 2 valid reactions between {MIN_REACTION_MS}–'
            f'{MAX_REACTION_MS} ms. Impossible or anticipatory clicks were removed.'
        )
        return False, errors, {'valid_trials': valid_trials}

    avg = round(sum(valid_trials) / len(valid_trials))
    reported = int(data.get('response_time_ms') or avg)
    if reported < MIN_REACTION_MS or reported > MAX_REACTION_MS:
        errors.append(f'Average reaction time {reported} ms is outside valid range.')

    cleaned = {
        'response_time_ms': avg,
        'valid_trials': valid_trials,
        'rejected_trials': [
            int(t) for t in trials
            if not (MIN_REACTION_MS <= int(t) <= MAX_REACTION_MS)
        ],
        'all_trials': [int(t) for t in trials],
    }
    return len(errors) == 0, errors, cleaned


def validate_memory_attempt(data):
    """Validate memory digit-span style attempt."""
    errors = []
    raw = data.get('raw_events') or {}
    score = float(data.get('score') or data.get('memory_score') or 0)
    levels = int(raw.get('levels_completed') or 0)
    total_rounds = int(raw.get('total_rounds') or 0)

    if score < MIN_MEMORY_SCORE or score > MAX_MEMORY_SCORE:
        errors.append('Memory score out of range.')
    if total_rounds < 3:
        errors.append('Incomplete memory task — finish at least 3 rounds.')
    if levels < 1 and score > 0:
        errors.append('Inconsistent memory metrics.')

    cleaned = {
        'memory_score': score,
        'levels_completed': levels,
        'total_rounds': total_rounds,
    }
    return len(errors) == 0, errors, cleaned


def validate_concentration_attempt(data):
    """Validate sustained-attention / go-no-go concentration attempt."""
    errors = []
    raw = data.get('raw_events') or {}
    score = float(data.get('score') or data.get('concentration_score') or 0)
    targets = int(raw.get('targets_shown') or 0)
    hits = int(raw.get('hits') or 0)
    false_alarms = int(raw.get('false_alarms') or 0)
    total_trials = int(raw.get('total_trials') or 0)

    if score < 0 or score > 100:
        errors.append('Concentration score out of range.')
    if total_trials < 20:
        errors.append('Incomplete concentration task — finish the full attention run.')
    if targets < 5:
        errors.append('Too few target stimuli for a valid concentration score.')

    cleaned = {
        'concentration_score': score,
        'targets_shown': targets,
        'hits': hits,
        'false_alarms': false_alarms,
        'total_trials': total_trials,
    }
    return len(errors) == 0, errors, cleaned


def summarize_mouse_metrics(raw_events):
    """Extract mouse movement / click-interval summary from client payload."""
    raw = raw_events or {}
    mouse = raw.get('mouse') or {}

    def _safe_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _safe_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    avg_interval = mouse.get('avg_click_interval_ms')
    try:
        avg_interval = round(float(avg_interval), 2) if avg_interval is not None else None
    except (TypeError, ValueError):
        avg_interval = None

    return {
        'mouse_distance_px': round(_safe_float(mouse.get('distance_px'), 0), 2),
        'mouse_move_count': _safe_int(mouse.get('move_count'), 0),
        'avg_click_interval_ms': avg_interval,
        'click_count': _safe_int(mouse.get('click_count'), 0),
        'click_intervals_ms': mouse.get('click_intervals_ms') or [],
    }


def build_validation_flags(errors, cleaned_extra=None):
    """Compact flags dict stored on the task / interaction record."""
    flags = {'errors': errors, 'rejected': bool(errors)}
    if cleaned_extra:
        flags.update(cleaned_extra)
    return flags
