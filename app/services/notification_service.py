"""
app/services/notification_service.py
────────────────────────────────────
Handles outbound notifications (Email) for the agent.
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class NotificationService:
    """Service for sending notifications via SMTP Email."""

    def __init__(self):
        self.server = settings.smtp_server
        self.port = settings.smtp_port
        self.user = settings.smtp_user
        self.password = settings.smtp_password
        self.to_email = settings.notification_email

        # Log loaded credentials for debugging (mask password)
        log.info(
            f"NotificationService init | server={self.server} | port={self.port} | "
            f"user={self.user} | to={self.to_email} | "
            f"password={'SET (' + str(len(self.password)) + ' chars)' if self.password else 'EMPTY'}"
        )

    async def send_message(self, message: str, html_preview_url: str = None) -> bool:
        """
        Sends an email notification.
        
        Args:
            message: The main message text.
            html_preview_url: Optional URL to include as a convenient clickable link.
            
        Returns:
            True if sent successfully, False otherwise.
        """
        # Check for missing SMTP credentials first
        missing = []
        if not self.server:
            missing.append("SMTP_SERVER")
        if not self.user:
            missing.append("SMTP_USER")
        if not self.password:
            missing.append("SMTP_PASSWORD")
        if not self.to_email:
            missing.append("NOTIFICATION_EMAIL")

        if missing:
            log.warning(f"SMTP credentials missing: {', '.join(missing)} — cannot send email.")
            # Fallback: write preview to static folder
            try:
                from pathlib import Path
                html_content = f"""
                <html><body>
                    <h2>🚀 New LinkedIn Draft Ready for Review</h2>
                    <p>{message}</p>
                    <p>Preview Link: <a href='{html_preview_url}'>{html_preview_url}</a></p>
                </body></html>
                """
                artifact_path = Path(r'C:/Users/samra/Documents/Project/linkedin-agent/app/static/email_preview.html')
                artifact_path.parent.mkdir(parents=True, exist_ok=True)
                artifact_path.write_text(html_content)
                log.info('Email preview written to static folder as fallback.')
            except Exception as ex:
                log.error(f"Failed to write fallback email preview: {ex}")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🚀 New LinkedIn Draft Ready for Review"
        msg["From"] = self.user
        msg["To"] = self.to_email

        # Create plain-text version
        text = f"{message}\n\nReview your draft here: {html_preview_url}"

        # Create clean HTML notification email with a clickable button
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>New LinkedIn Draft Ready</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f9;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#0077b5 0%,#005e96 100%);padding:36px 40px;text-align:center;">
              <p style="margin:0;font-size:32px;">🤖</p>
              <h1 style="margin:12px 0 4px;color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.3px;">LinkedIn AI Agent</h1>
              <p style="margin:0;color:rgba(255,255,255,0.8);font-size:14px;">Autonomous Post Generation</p>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:40px 40px 32px;">
              <h2 style="margin:0 0 12px;color:#0077b5;font-size:18px;font-weight:700;">🚀 New Draft Ready for Review</h2>
              <p style="margin:0 0 24px;color:#444;font-size:15px;line-height:1.6;">{message.replace(chr(10), '<br>')}</p>
              <hr style="border:none;border-top:1px solid #e8eaf0;margin:24px 0;">
              <p style="margin:0 0 24px;color:#666;font-size:14px;line-height:1.5;">
                Your AI agent has generated a new LinkedIn post draft. Click the button below to review the full content, make any edits, and approve it for publishing.
              </p>
              <!-- CTA Button -->
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td align="center">
                    <a href="{html_preview_url}"
                       style="display:inline-block;background:linear-gradient(135deg,#0077b5,#005e96);color:#ffffff;text-decoration:none;font-size:15px;font-weight:700;padding:14px 40px;border-radius:8px;letter-spacing:0.3px;">
                      Review Draft &rarr;
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin:24px 0 0;text-align:center;color:#aaa;font-size:12px;">
                Or copy this link: <a href="{html_preview_url}" style="color:#0077b5;word-break:break-all;">{html_preview_url}</a>
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background:#f8fafc;padding:20px 40px;text-align:center;border-top:1px solid #e8eaf0;">
              <p style="margin:0;color:#bbb;font-size:12px;">LinkedIn AI Agent &bull; Automated notification &bull; Do not reply to this email</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

        log.info("Built clean notification email with preview link")
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        import asyncio

        def _send_sync() -> bool:
            try:
                log.info(f"Connecting to SMTP server {self.server}:{self.port}...")
                context = ssl.create_default_context()
                if self.port == 465:
                    with smtplib.SMTP_SSL(self.server, self.port, context=context, timeout=15) as server:
                        server.login(self.user, self.password)
                        server.sendmail(self.user, self.to_email, msg.as_string())
                else:
                    with smtplib.SMTP(self.server, self.port, timeout=15) as server:
                        server.starttls(context=context)
                        server.login(self.user, self.password)
                        server.sendmail(self.user, self.to_email, msg.as_string())
                
                log.info(f"Email notification sent successfully to {self.to_email}")
                return True
            except smtplib.SMTPAuthenticationError as e:
                log.error(f"SMTP Authentication FAILED: {e}")
                return False
            except Exception as e:
                log.warning(f"SMTP primary attempt failed ({e}), trying STARTTLS fallback on port 587...")
                try:
                    context = ssl.create_default_context()
                    with smtplib.SMTP(self.server, 587, timeout=15) as server:
                        server.starttls(context=context)
                        server.login(self.user, self.password)
                        server.sendmail(self.user, self.to_email, msg.as_string())
                    log.info(f"Email sent successfully via STARTTLS (port 587) to {self.to_email}")
                    return True
                except Exception as fallback_err:
                    log.error(f"SMTP fallback also failed: {fallback_err}", exc_info=True)
                    return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _send_sync)
