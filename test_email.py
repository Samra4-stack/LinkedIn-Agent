"""Quick test to verify email sending works."""
import asyncio
import sys
sys.path.insert(0, '.')

from app.services.notification_service import NotificationService

async def test_email():
    notifier = NotificationService()
    result = await notifier.send_message(
        message="This is a test email from your LinkedIn AI Agent.\n\nIf you received this, email notifications are working!",
        html_preview_url="http://localhost:8000/api/v1/preview/1/view"
    )
    if result:
        print("\n✅ Email sent successfully! Check your inbox.")
    else:
        print("\n❌ Email failed to send. Check the error messages above.")

asyncio.run(test_email())
