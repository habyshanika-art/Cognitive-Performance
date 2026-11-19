"""
Brevo Transactional Email
-------------------------
Sends emails via Brevo API v3. API key stays on the backend only
(environment variable BREVO_API_KEY — never expose to the browser).
"""

import json
import urllib.error
import urllib.request

from flask import current_app


def brevo_configured():
    return bool(current_app.config.get('BREVO_API_KEY'))


def send_brevo_email(to_email, subject, text_body, html_body=None, to_name=None):
    """
    Send one transactional email through Brevo.
    Returns (ok: bool, detail: str).
    """
    api_key = current_app.config.get('BREVO_API_KEY', '')
    if not api_key:
        return False, 'BREVO_API_KEY is not configured'

    sender_email = current_app.config.get('BREVO_SENDER_EMAIL') or current_app.config.get(
        'MAIL_DEFAULT_SENDER', 'noreply@cognitivemonitor.local'
    )
    sender_name = current_app.config.get('BREVO_SENDER_NAME', 'CogMonitor')

    payload = {
        'sender': {'name': sender_name, 'email': sender_email},
        'to': [{'email': to_email, 'name': to_name or to_email}],
        'replyTo': {'email': sender_email, 'name': sender_name},
        'subject': subject,
        'textContent': text_body,
        'htmlContent': html_body or f'<pre style="font-family:sans-serif">{text_body}</pre>',
        # Helps Brevo classify this as transactional (OTP), not marketing
        'tags': ['transactional', 'email-verification', 'otp'],
        'headers': {
            'X-Mailin-custom': 'cogmonitor-otp',
            'charset': 'utf-8',
        },
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        'https://api.brevo.com/v3/smtp/email',
        data=data,
        method='POST',
        headers={
            'api-key': api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            if 200 <= resp.status < 300:
                return True, body or 'sent'
            return False, f'Brevo HTTP {resp.status}: {body}'
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        current_app.logger.warning('Brevo send failed: %s %s', exc.code, detail)
        return False, f'Brevo HTTP {exc.code}: {detail}'
    except Exception as exc:
        current_app.logger.warning('Brevo send error: %s', exc)
        return False, str(exc)
