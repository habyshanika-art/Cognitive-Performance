"""
Email OTP Verification
----------------------
6-digit OTP, 10-minute expiry, 60s resend cooldown, max 5 attempts.
OTP is stored hashed — never keep the plaintext code in the database.
"""

import secrets
from datetime import datetime, timedelta

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.utils.brevo_email import brevo_configured, send_brevo_email

OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 10
RESEND_COOLDOWN_SECONDS = 60
MAX_OTP_ATTEMPTS = 5


def _generate_otp():
    return f'{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}'


def issue_email_verification_otp(user, force=False):
    """
    Create a new hashed OTP for the user and send it via Brevo.
    Returns (ok, message, plaintext_otp_or_None).
    plaintext is only returned in DEBUG when Brevo is not configured.
    """
    if getattr(user, 'email_verified', False):
        return True, 'Email is already verified.', None

    now = datetime.utcnow()
    last_sent = getattr(user, 'email_otp_sent_at', None)
    if (
        not force
        and last_sent
        and (now - last_sent).total_seconds() < RESEND_COOLDOWN_SECONDS
    ):
        wait = RESEND_COOLDOWN_SECONDS - int((now - last_sent).total_seconds())
        return False, f'Please wait {wait}s before requesting another code.', None

    otp = _generate_otp()
    user.email_otp_hash = generate_password_hash(otp)
    user.email_otp_expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)
    user.email_otp_attempts = 0
    user.email_otp_sent_at = now
    db.session.commit()

    from app.utils.email_templates import build_otp_email_html

    # Keep subject simple — flashy marketing-style subjects land in spam more often
    subject = 'Your CogMonitor verification code'
    text_body = (
        f'Hi {user.first_name},\n\n'
        f'Your CogMonitor verification code is {otp}.\n'
        f'It expires in {OTP_EXPIRY_MINUTES} minutes.\n\n'
        f'Enter this code on the verification page to finish creating your account.\n'
        f'If you did not sign up for CogMonitor, you can ignore this message.\n\n'
        f'Thanks,\n'
        f'CogMonitor\n'
    )

    html_body = build_otp_email_html(
        user.first_name, otp, expiry_minutes=OTP_EXPIRY_MINUTES
    )

    if brevo_configured():
        ok, detail = send_brevo_email(
            user.email, subject, text_body, html_body=html_body, to_name=user.full_name
        )
        if not ok:
            return False, f'Could not send verification email ({detail}).', None
        return True, 'Verification code sent to your email.', None

    # Local/dev fallback — never expose OTP to the browser in production
    if current_app.debug:
        current_app.logger.warning(
            'BREVO_API_KEY missing — DEBUG OTP for %s is %s', user.email, otp
        )
        return True, (
            'Brevo is not configured. DEBUG mode: check the server console for the OTP.'
        ), otp

    return False, (
        'Email delivery is not configured. Ask the administrator to set BREVO_API_KEY.'
    ), None


def verify_email_otp(user, code):
    """
    Validate OTP. Returns (ok, message).
    """
    if getattr(user, 'email_verified', False):
        return True, 'Email is already verified.'

    code = (code or '').strip()
    if not code.isdigit() or len(code) != OTP_LENGTH:
        return False, f'Enter the {OTP_LENGTH}-digit code from your email.'

    if not user.email_otp_hash or not user.email_otp_expires_at:
        return False, 'No verification code found. Please request a new one.'

    if datetime.utcnow() > user.email_otp_expires_at:
        return False, 'This code has expired. Please request a new one.'

    attempts = int(user.email_otp_attempts or 0)
    if attempts >= MAX_OTP_ATTEMPTS:
        return False, 'Too many incorrect attempts. Request a new code.'

    if not check_password_hash(user.email_otp_hash, code):
        user.email_otp_attempts = attempts + 1
        db.session.commit()
        remaining = MAX_OTP_ATTEMPTS - user.email_otp_attempts
        if remaining <= 0:
            return False, 'Too many incorrect attempts. Request a new code.'
        return False, f'Incorrect code. {remaining} attempt(s) remaining.'

    user.email_verified = True
    user.email_verified_at = datetime.utcnow()
    user.email_otp_hash = None
    user.email_otp_expires_at = None
    user.email_otp_attempts = 0
    user.email_otp_sent_at = None
    db.session.commit()
    return True, 'Email verified successfully. You can log in now.'


def seconds_until_resend(user):
    last_sent = getattr(user, 'email_otp_sent_at', None)
    if not last_sent:
        return 0
    elapsed = (datetime.utcnow() - last_sent).total_seconds()
    remaining = RESEND_COOLDOWN_SECONDS - int(elapsed)
    return max(0, remaining)
