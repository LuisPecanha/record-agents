import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise RuntimeError("ANTHROPIC_API_KEY not found. Please check your .env file.")

import anthropic
from apscheduler.schedulers.blocking import BlockingScheduler

from integrations.sheets_client import SheetsClient
from integrations.gmail_client import GmailClient

from agents.email_triage import run as email_triage_run
from agents.release_calendar import run as release_calendar_run
from agents.demo_screening import run as demo_screening_run
from agents.press_kit import run as press_kit_run

client = anthropic.Anthropic(api_key=api_key)

message = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=64,
    messages=[{"role": "user", "content": "Say hello from Balters Records agent system."}],
)
print(message.content[0].text)  # type: ignore[union-attr]

sheets = SheetsClient()
gmail = GmailClient()
claude = client

scheduler = BlockingScheduler()

scheduler.add_job(email_triage_run, "interval", minutes=60)
scheduler.add_job(release_calendar_run, "interval", minutes=60)
scheduler.add_job(demo_screening_run, "interval", minutes=60)
scheduler.add_job(press_kit_run, "interval", minutes=60)

print("[boot] Running all agents on startup...")
email_triage_run(gmail=gmail, sheets=sheets, claude=claude)
release_calendar_run(sheets=sheets, gmail=gmail)
demo_screening_run(sheets=sheets, gmail=gmail, claude=claude)
press_kit_run(sheets=sheets, gmail=gmail, claude=claude)
print("[boot] Startup run complete.")

print("Balters Agents running...")

try:
    scheduler.start()
except KeyboardInterrupt:
    scheduler.shutdown()
