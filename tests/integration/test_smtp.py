"""Manual test: verifies SMTP sending via GmailClient."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from integrations.gmail_client import GmailClient

to = os.getenv("EMAIL_EQUIPE")
if not to:
    print("EMAIL_EQUIPE not found in .env.")
    sys.exit(1)

try:
    gmail = GmailClient()
except Exception as e:
    print(f"GmailClient init failed: {e}")
    sys.exit(1)

subject = "[Balters TEST] SMTP verification"
body = (
    "This is an automated test email sent by the Balters Agents system.\n\n"
    "It confirms that SMTP sending is working correctly via Gmail App Password.\n\n"
    "You can ignore this message."
)

success = gmail.send_email(to=to, subject=subject, body=body)

if success:
    print(f"Email sent successfully to {to}.")
else:
    print("Failed to send email.")
    sys.exit(1)
