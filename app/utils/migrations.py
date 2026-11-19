"""Database schema migrations for existing installations."""

from sqlalchemy import text, inspect

from app import db


def run_migrations():
    """Apply incremental schema updates for existing databases."""
    _apply_schema_migrations()
    try:
        from app.utils.monitoring import backfill_aggregated_cycles
        backfill_aggregated_cycles()
    except Exception:
        pass
    try:
        _backfill_anonymised_ids()
    except Exception:
        pass


def _column_names(table):
    inspector = inspect(db.engine)
    if table not in inspector.get_table_names():
        return set()
    return {c['name'] for c in inspector.get_columns(table)}


def _add_column_if_missing(table, column_name, ddl):
    cols = _column_names(table)
    if column_name not in cols:
        db.session.execute(text(f'ALTER TABLE `{table}` ADD COLUMN {ddl}'))
        db.session.commit()


def _apply_schema_migrations():
    inspector = inspect(db.engine)
    user_columns = _column_names('user')

    if 'username' not in user_columns:
        db.session.execute(text(
            "ALTER TABLE user ADD COLUMN username VARCHAR(80) UNIQUE AFTER role_id"
        ))
        db.session.execute(text(
            "UPDATE user SET username = CONCAT("
            "SUBSTRING_INDEX(email, '@', 1), '_', id) WHERE username IS NULL"
        ))
        db.session.commit()

    if 'profile_picture' not in user_columns:
        db.session.execute(text(
            "ALTER TABLE user ADD COLUMN profile_picture VARCHAR(255) AFTER phone"
        ))
        db.session.commit()

    for col, default in (
        ('notify_assessment_reminders', '1'),
        ('notify_performance_alerts', '1'),
        ('notify_publications', '1'),
        ('notify_email', '1'),
        ('consent_given', '0'),
        ('data_withdrawn', '0'),
    ):
        if col not in _column_names('user'):
            db.session.execute(text(
                f"ALTER TABLE user ADD COLUMN {col} TINYINT(1) DEFAULT {default}"
            ))
            db.session.commit()

    _add_column_if_missing(
        'user', 'anonymised_id',
        'anonymised_id VARCHAR(20) UNIQUE NULL'
    )
    _add_column_if_missing(
        'user', 'consent_given_at',
        'consent_given_at DATETIME NULL'
    )
    _add_column_if_missing(
        'user', 'consent_version',
        'consent_version VARCHAR(20) NULL'
    )

    # Email verification columns (Brevo OTP)
    adding_verified = 'email_verified' not in _column_names('user')
    if adding_verified:
        db.session.execute(text(
            "ALTER TABLE user ADD COLUMN email_verified TINYINT(1) DEFAULT 0"
        ))
        db.session.commit()
        # Existing accounts (pre-feature) remain able to log in
        db.session.execute(text("UPDATE user SET email_verified = 1"))
        db.session.commit()
    _add_column_if_missing('user', 'email_verified_at', 'email_verified_at DATETIME NULL')
    _add_column_if_missing('user', 'email_otp_hash', 'email_otp_hash VARCHAR(255) NULL')
    _add_column_if_missing('user', 'email_otp_expires_at', 'email_otp_expires_at DATETIME NULL')
    _add_column_if_missing(
        'user', 'email_otp_attempts', 'email_otp_attempts INT DEFAULT 0'
    )
    _add_column_if_missing('user', 'email_otp_sent_at', 'email_otp_sent_at DATETIME NULL')

    if 'notification' not in inspector.get_table_names():
        db.create_all()

    # Ensure new tables exist (email_message, etc.)
    db.create_all()

    if 'task' in inspector.get_table_names():
        task_columns = _column_names('task')
        if 'cycle_number' not in task_columns:
            db.session.execute(text(
                "ALTER TABLE task ADD COLUMN cycle_number INT NOT NULL DEFAULT 1 "
                "AFTER attempt_number"
            ))
            db.session.commit()

        _add_column_if_missing('task', 'device_type', "device_type VARCHAR(20) NULL")
        _add_column_if_missing('task', 'is_practice', "is_practice TINYINT(1) DEFAULT 0")
        _add_column_if_missing('task', 'is_valid', "is_valid TINYINT(1) DEFAULT 1")
        _add_column_if_missing('task', 'validation_flags', "validation_flags JSON NULL")

        try:
            db.session.execute(text(
                "UPDATE task SET is_valid = 1 WHERE is_valid IS NULL"
            ))
            db.session.execute(text(
                "UPDATE task SET is_practice = 0 WHERE is_practice IS NULL"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()

        # Expand status enum to include rejected
        try:
            db.session.execute(text(
                "ALTER TABLE task MODIFY COLUMN status "
                "ENUM('in_progress','completed','abandoned','rejected') "
                "DEFAULT 'in_progress'"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()

    if 'cognitive_metrics' in inspector.get_table_names():
        cm_columns = _column_names('cognitive_metrics')
        if 'cycle_number' not in cm_columns:
            db.session.execute(text(
                "ALTER TABLE cognitive_metrics ADD COLUMN cycle_number INT NOT NULL DEFAULT 1 "
                "AFTER attempt_number"
            ))
            db.session.commit()

    if 'aggregated_metrics' in inspector.get_table_names():
        for col, ddl in (
            ('typing_deviation', 'typing_deviation DECIMAL(10,2) NULL'),
            ('reaction_deviation', 'reaction_deviation DECIMAL(10,2) NULL'),
            ('memory_deviation', 'memory_deviation DECIMAL(10,2) NULL'),
            ('concentration_deviation', 'concentration_deviation DECIMAL(10,2) NULL'),
            ('overall_deviation', 'overall_deviation DECIMAL(10,2) NULL'),
            ('is_baseline_cycle', 'is_baseline_cycle TINYINT(1) DEFAULT 0'),
            ('is_flagged', 'is_flagged TINYINT(1) DEFAULT 0'),
        ):
            _add_column_if_missing('aggregated_metrics', col, ddl)

    # Expand notification_type ENUM used by cycle/alert/consent flows
    if 'notification' in inspector.get_table_names():
        try:
            db.session.execute(text(
                "ALTER TABLE notification MODIFY COLUMN notification_type "
                "ENUM('feedback','publication','assessment_reminder','system',"
                "'performance_alert','cycle_complete','consent','password_code') "
                "NOT NULL"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()


def _backfill_anonymised_ids():
    from app.models.user import User
    users = User.query.filter(
        (User.anonymised_id.is_(None)) | (User.anonymised_id == '')
    ).all()
    for user in users:
        user.ensure_anonymised_id()
    if users:
        db.session.commit()

    # Disambiguate username collisions from email-prefix backfill
    try:
        rows = db.session.execute(text(
            "SELECT username, COUNT(*) AS c FROM user "
            "WHERE username IS NOT NULL GROUP BY username HAVING c > 1"
        )).fetchall()
        for row in rows:
            username = row[0]
            dupes = User.query.filter_by(username=username).order_by(User.id).all()
            for idx, user in enumerate(dupes):
                if idx == 0:
                    continue
                base = (username or 'user')[:70]
                candidate = f'{base}{user.id}'
                n = 1
                while User.query.filter_by(username=candidate).first():
                    candidate = f'{base}{user.id}_{n}'
                    n += 1
                user.username = candidate
        if rows:
            db.session.commit()
    except Exception:
        db.session.rollback()
