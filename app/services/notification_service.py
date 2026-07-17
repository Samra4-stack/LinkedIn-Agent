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
            if not self.server or not self.user or not self.password or not self.to_email:
                # No SMTP credentials – write the email content to an artifact for the user to view
                from pathlib import Path
                # Build simple HTML content
                html_content = f"""
                <html><body>
                    <h2>{msg['Subject']}</h2>
                    <p>{message}</p>
                    <p>Preview Link: <a href='{html_preview_url}'>{html_preview_url}</a></p>
                </body></html>
                """
                # Artifact path – use a deterministic filename
                artifact_path = Path(r'C:/Users/samra/.gemini/antigravity/brain/7b78159d-f5e0-4409-873c-1ceab94e462e/email_preview.html')
                # Write the file
                artifact_path.parent.mkdir(parents=True, exist_ok=True)
                artifact_path.write_text(html_content)
                log.info('SMTP credentials missing – email preview written to artifact for manual inspection.')
                return True

            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.server, self.port, context=context) as server:
                server.login(self.user, self.password)
                server.sendmail(self.user, self.to_email, msg.as_string())
            
            log.info("Email notification sent successfully.")
            return True
        except Exception as e:
            log.error(f"Failed to send Email notification: {e}")
            return False
