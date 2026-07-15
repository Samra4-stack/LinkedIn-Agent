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

    async def send_message(self, message: str, html_preview_url: str = None) -> bool:
        """
        Sends an email notification.
        
        Args:
            message: The main message text.
            html_preview_url: Optional URL to include as a convenient clickable link.
            
        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.server or not self.user or not self.password or not self.to_email:
            log.warning("Email credentials not fully configured. Skipping notification.")
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

        msg.attach(MIMEText(text, "plain"))
        if html_preview_url:
            msg.attach(MIMEText(html, "html"))

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.server, self.port, context=context) as server:
                server.login(self.user, self.password)
                server.sendmail(self.user, self.to_email, msg.as_string())
            
            log.info("Email notification sent successfully.")
            return True
        except Exception as e:
            log.error(f"Failed to send Email notification: {e}")
            return False
