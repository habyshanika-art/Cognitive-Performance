"""
Branded HTML email templates — CogMonitor black neon notice style.
Table-based layout for email client compatibility.
"""

from datetime import datetime

from flask import current_app


def _contact_email():
    try:
        from app.utils.helpers import get_system_setting
        return (
            get_system_setting('contact_email', '')
            or current_app.config.get('BREVO_SENDER_EMAIL')
            or 'habyshanika@gmail.com'
        )
    except Exception:
        return current_app.config.get('BREVO_SENDER_EMAIL') or 'habyshanika@gmail.com'


def build_notice_email_html(
    title,
    greeting,
    intro,
    sections=None,
    highlight_label=None,
    highlight_value=None,
    footer_note=None,
):
    """
    Formal notice layout (header logo + meta + body) in CogMonitor black theme.
    """
    contact = _contact_email()
    site = 'CogMonitor'
    # Avoid localhost URLs in email — they increase spam scoring
    website = current_app.config.get('PUBLIC_SITE_URL', 'CogMonitor Research Platform')
    today = datetime.utcnow().strftime('%B %d, %Y')
    sections = sections or []
    footer_note = footer_note or (
        'CogMonitor monitors interaction patterns for research purposes only '
        'and does not provide medical diagnoses.'
    )

    sections_html = ''
    for heading, body in sections:
        sections_html += f'''
        <tr><td style="padding:18px 0 6px 0;">
          <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:700;color:#40ff80;letter-spacing:0.3px;">
            {heading}
          </p>
        </td></tr>
        <tr><td style="padding:0 0 4px 0;">
          <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.65;color:#b8ecf5;">
            {body}
          </p>
        </td></tr>
        '''

    highlight_html = ''
    if highlight_value:
        highlight_html = f'''
        <tr><td style="padding:22px 0 8px 0;" align="center">
          <p style="margin:0 0 10px 0;font-family:Arial,Helvetica,sans-serif;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#5ec8d6;">
            {highlight_label or 'Verification Code'}
          </p>
          <div style="display:inline-block;padding:16px 28px;border:2px solid #ff007f;border-radius:12px;background:#12122a;box-shadow:0 0 18px rgba(255,0,127,0.35);">
            <span style="font-family:Consolas,Monaco,monospace;font-size:32px;font-weight:700;letter-spacing:10px;color:#ffe600;">
              {highlight_value}
            </span>
          </div>
        </td></tr>
        '''

    return f'''
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#05050f;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#05050f;padding:28px 12px;">
    <tr><td align="center">
      <table role="presentation" width="640" cellspacing="0" cellpadding="0" border="0" style="max-width:640px;width:100%;background:#0f0f1e;border:1px solid rgba(0,240,255,0.35);border-radius:16px;overflow:hidden;box-shadow:0 0 40px rgba(255,0,127,0.18);">

        <!-- Header -->
        <tr>
          <td style="padding:22px 28px 16px 28px;background:linear-gradient(135deg,#12122a 0%,#0a0a18 100%);border-bottom:1px solid rgba(255,0,127,0.45);">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
              <tr>
                <td valign="middle" width="64">
                  <div style="width:56px;height:56px;border-radius:50%;background:#15152a;border:2px solid #00f0ff;text-align:center;line-height:52px;box-shadow:0 0 16px rgba(0,240,255,0.35);">
                    <span style="font-family:Arial,Helvetica,sans-serif;font-size:18px;font-weight:800;color:#ff007f;letter-spacing:0.5px;">CM</span>
                  </div>
                </td>
                <td valign="middle" style="padding-left:14px;">
                  <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:20px;font-weight:800;color:#00f0ff;letter-spacing:1px;">
                    CogMonitor
                  </p>
                  <p style="margin:4px 0 0 0;font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#40ff80;">
                    Cognitive Performance Monitoring System
                  </p>
                </td>
                <td valign="middle" align="right" style="font-family:Arial,Helvetica,sans-serif;font-size:11px;line-height:1.55;color:#5ec8d6;">
                  {contact}<br>
                  {website}<br>
                  Research Platform<br>
                  @CogMonitor
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Accent bar -->
        <tr><td style="height:3px;background:linear-gradient(90deg,#ff007f,#00f0ff,#40ff80,#ffe600);"></td></tr>

        <!-- Title + meta -->
        <tr>
          <td style="padding:28px 32px 8px 32px;">
            <h1 style="margin:0 0 18px 0;text-align:center;font-family:Arial,Helvetica,sans-serif;font-size:22px;line-height:1.3;font-weight:800;color:#00f0ff;">
              {title}
            </h1>
            <p style="margin:0 0 4px 0;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#7af5ff;">{today}</p>
            <p style="margin:0 0 4px 0;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#b8ecf5;">
              <strong style="color:#ffe600;">To:</strong> Account Holder
            </p>
            <p style="margin:0 0 4px 0;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#b8ecf5;">
              <strong style="color:#ffe600;">From:</strong> {site} Security
            </p>
            <p style="margin:0 0 16px 0;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#b8ecf5;">
              <strong style="color:#ffe600;">Subject:</strong> {title}
            </p>
            <div style="border-top:1px solid rgba(0,240,255,0.25);padding-top:16px;">
              <p style="margin:0 0 12px 0;font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#00f0ff;">
                {greeting}
              </p>
              <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.65;color:#b8ecf5;">
                {intro}
              </p>
            </div>
          </td>
        </tr>

        <!-- Sections + OTP -->
        <tr>
          <td style="padding:4px 32px 8px 32px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
              {sections_html}
              {highlight_html}
            </table>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 32px 28px 32px;">
            <div style="border-top:1px solid rgba(255,0,127,0.3);padding-top:16px;">
              <p style="margin:0 0 8px 0;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.55;color:#5ec8d6;">
                {footer_note}
              </p>
              <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#40ff80;">
                — CogMonitor System
              </p>
            </div>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
'''


def build_otp_email_html(first_name, otp, expiry_minutes=10):
    """OTP verification notice in branded black theme."""
    return build_notice_email_html(
        title='Account Verification',
        greeting=f'Hi {first_name},',
        intro=(
            'Thanks for creating your CogMonitor account. '
            'Use the verification code below to confirm your email and activate access.'
        ),
        sections=[
            (
                'Why this email',
                'We verify email addresses so only the account owner can activate '
                'participant access in the research system.',
            ),
            (
                'Next step',
                f'Enter the 6-digit code on the verification page within {expiry_minutes} minutes. '
                'If you did not create this account, ignore this email.',
            ),
        ],
        highlight_label='Verification code',
        highlight_value=otp,
    )
