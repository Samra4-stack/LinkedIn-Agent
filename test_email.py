"""Quick script to verify email notifications are working correctly."""
import asyncio
import sys
sys.path.insert(0, '.')

from app.services.notification_service import NotificationService


async def test_email():
    notifier = NotificationService()
    result = await notifier.send_message(
        message=(
            "New LinkedIn Draft Ready!\n\n"
            "Topic: The Future of AI in the Workplace\n"
            "Length: 1,240 characters\n\n"
            "Your AI agent has generated a new post draft. "
            "Click the button below to review the full content, make any edits, and approve it for publishing."
        ),
        html_preview_url="https://linked-in-agent-lilac.vercel.app/api/v1/preview/72/view"
    )
    if result:
        print("\nEmail sent successfully! Check your inbox.")
    else:
        print("\nEmail failed to send. Check the error messages above.")


asyncio.run(test_email())
