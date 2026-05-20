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
from apscheduler.triggers.cron import CronTrigger

from integrations.sheets_client import SheetsClient
from integrations.gmail_client import GmailClient
from integrations.calendar_client import CalendarClient

from agents.email_triage import run as email_triage_run
from agents.release_calendar import run as release_calendar_run
from agents.demo_screening import run as demo_screening_run
from agents.press_kit import run as press_kit_run
from agents.draft_approval import run as draft_approval_run
from automations.deadline_tracking import run_daily, run_weekly

client = anthropic.Anthropic(api_key=api_key)

message = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=64,
    messages=[{"role": "user", "content": "Say hello from Balters Records agent system."}],
)
print(message.content[0].text)  # type: ignore[union-attr]

sheets = SheetsClient()
gmail = GmailClient()
calendar = CalendarClient()
claude = client

scheduler = BlockingScheduler()

# NOTE: BlockingScheduler runs all jobs on a single thread — jobs cannot overlap.
# If email_triage_run (60 min interval) takes longer than expected due to API latency,
# it will block draft_approval_run (15 min interval) from firing on time.
# This is acceptable at current volume. If it becomes a problem in production,
# switch to BackgroundScheduler with coalescing enabled on the job store.
scheduler.add_job(email_triage_run, "interval", minutes=60)
scheduler.add_job(release_calendar_run, "interval", minutes=60, kwargs={"sheets": sheets, "gmail": gmail, "calendar": calendar})
scheduler.add_job(demo_screening_run, "interval", minutes=60)
scheduler.add_job(press_kit_run, "interval", minutes=60)
scheduler.add_job(draft_approval_run, "interval", minutes=15, kwargs={"gmail": gmail, "sheets": sheets})
scheduler.add_job(
    lambda: run_daily(sheets, gmail, calendar),
    CronTrigger(hour=9, minute=0),
    id="deadline_tracking_daily",
    name="Deadline Tracking — Daily Alerts",
)
scheduler.add_job(
    lambda: run_weekly(sheets, gmail),
    CronTrigger(day_of_week="mon", hour=9, minute=0),
    id="deadline_tracking_weekly",
    name="Deadline Tracking — Weekly Summary",
)

print("[boot] Running all agents on startup...")
email_triage_run(gmail=gmail, sheets=sheets, claude=claude)
release_calendar_run(sheets=sheets, gmail=gmail, calendar=calendar)
demo_screening_run(sheets=sheets, gmail=gmail, claude=claude)
press_kit_run(sheets=sheets, gmail=gmail, claude=claude)
print("[boot] Startup run complete.")

print("Balters Agents running...")

try:
    scheduler.start()
except KeyboardInterrupt:
    scheduler.shutdown()
