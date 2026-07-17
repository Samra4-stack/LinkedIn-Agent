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
        text = f"{message}\n\nPreview Link: {html_preview_url}"
        
        # Create HTML version
        html = f"""
        <html>
          <body>
            <h2>New LinkedIn Draft Ready!</h2>
            <p>{message.replace(chr(10), '<br>')}</p>
            <br>
            <a href="{html_preview_url}" style="display: inline-block; padding: 10px 20px; background-color: #0077b5; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">
              Preview Draft Here
            </a>
          </body>
        </html>
        """

        msg.attach(MIMEText(text, "plain", "utf-8"))
        if html_preview_url:
            msg.attach(MIMEText(html, "html", "utf-8"))

        try:
            log.info(f"Connecting to SMTP server {self.server}:{self.port} using SMTP_SSL...")
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.server, self.port, context=context) as server:
                log.info("SMTP_SSL connection established. Logging in...")
                server.login(self.user, self.password)
                log.info("SMTP login successful. Sending email...")
                server.sendmail(self.user, self.to_email, msg.as_string())
            
            log.info(f"Email notification sent successfully to {self.to_email}")
            return True
        except smtplib.SMTPAuthenticationError as e:
            log.error(
                f"SMTP Authentication FAILED: {e} — "
                f"Make sure you are using a Gmail App Password (not your regular password). "
                f"Generate one at https://myaccount.google.com/apppasswords"
            )
            return False
        except smtplib.SMTPException as e:
            log.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            log.error(f"Failed to send email notification: {e}", exc_info=True)
            return False
