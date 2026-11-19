"""
Email Notification Service
--------------------------
Stores every message in the user inbox and optionally sends via SMTP.
Works offline: without SMTP config, messages still appear in Profile → Email.
"""

import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import current_app

from app import db
from app.models.email_message import EmailMessage
from app.models.notification import Notification

# Map inbox/email categories onto Notification.notification_type ENUM values
_NOTIFICATION_TYPE_MAP = {
    'feedback': 'feedback',
    'publication': 'publication',
    'assessment_reminder': 'assessment_reminder',
    'system': 'system',
    'performance_alert': 'performance_alert',
    'cycle_complete': 'cycle_complete',
    'consent': 'consent',
    'password_code': 'password_code',
    'notification': 'system',
    'alert': 'performance_alert',
}


def _notification_type_for(category):
    """Map free-form email category to a valid notification ENUM value."""
    return _NOTIFICATION_TYPE_MAP.get(category or 'system', 'system')


def _smtp_configured():
    return bool(current_app.config.get('MAIL_SERVER') and current_app.config.get('MAIL_USERNAME'))


def _send_smtp(to_email, subject, body):
    """Attempt SMTP delivery. Returns True on success."""
    if not _smtp_configured():
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = current_app.config.get('MAIL_DEFAULT_SENDER', current_app.config['MAIL_USERNAME'])
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        host = current_app.config['MAIL_SERVER']
        port = int(current_app.config.get('MAIL_PORT', 587))
        use_tls = current_app.config.get('MAIL_USE_TLS', True)
        username = current_app.config['MAIL_USERNAME']
        password = current_app.config.get('MAIL_PASSWORD', '')

        with smtplib.SMTP(host, port, timeout=15) as server:
            if use_tls:
                server.starttls()
            if username:
                server.login(username, password)
            server.send_message(msg)
        return True
    except Exception as exc:
        current_app.logger.warning('SMTP send failed: %s', exc)
        return False


def send_user_email(user, subject, body, category='notification', code=None,
                    also_notify=True, link_url=None, commit=True):
    """
    Create an inbox email for the user and try SMTP if configured.
    Also creates an in-app Notification when also_notify=True.
    Set commit=False when calling inside an open DB transaction.
    """
    if not user or not getattr(user, 'email', None):
        return None

    smtp_ok = False
    if getattr(user, 'notify_email', True):
        smtp_ok = _send_smtp(user.email, subject, body)

    sent_via = 'both' if smtp_ok else 'inbox'
    message = EmailMessage(
        user_id=user.id,
        subject=subject,
        body=body,
        category=category,
        code=code,
        sent_via=sent_via,
    )
    db.session.add(message)

    if also_notify:
        notif = Notification(
            user_id=user.id,
            notification_type=_notification_type_for(category),
            title=subject,
            message=body[:500],
            link_url=link_url or '/user/emails',
        )
        db.session.add(notif)

    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return message


def generate_password_reset_code(user):
    """Generate a 6-digit code, store as email, and optionally SMTP-send it."""
    code = f'{secrets.randbelow(1000000):06d}'
    subject = 'Your CogMonitor password reset code'
    body = (
        f'Hello {user.first_name},\n\n'
        f'Your password reset code is: {code}\n\n'
        f'This code is for your CogMonitor account ({user.email}).\n'
        f'If you did not request a reset, you can ignore this message.\n\n'
        f'— CogMonitor System\n'
        f'This system does not provide medical diagnoses.'
    )
    send_user_email(
        user, subject, body,
        category='password_code',
        code=code,
        also_notify=False,  # inbox-only; avoid duplicate/invalid notify types
        link_url='/user/emails',
    )
    return code


def email_system_notice(user, subject, body, category='system'):
    """Generic system email to inbox (+ SMTP when available)."""
    send_user_email(user, subject, body, category=category, also_notify=True)
