"""Manual test for CalendarClient — auth, create, and delete."""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from integrations.calendar_client import CalendarClient


def run_auth() -> None:
    client = CalendarClient()
    now = datetime.now(timezone.utc)
    time_min = now.strftime("%Y-%m-%dT00:00:00Z")
    time_max = (now + timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
    events = client.list_events(time_min=time_min, time_max=time_max)
    if events:
        for event in events:
            print(event.get("summary", "(no summary)"))
    else:
        print("No events found")
    print("Auth OK — Calendar access confirmed")


def run_create() -> None:
    client = CalendarClient()
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    event_id = client.create_event(
        summary="[TEST] Validação — Balters",
        date=tomorrow,
        description="Evento de teste do CalendarClient",
    )
    print(f"Event created — ID: {event_id}")


def run_delete(event_id: str) -> None:
    client = CalendarClient()
    client.delete_event(event_id)
    print(f"Event deleted — ID: {event_id}")


def run_purge() -> None:
    client = CalendarClient()
    events = client.list_events(time_min="2020-01-01T00:00:00Z", time_max="2030-01-01T00:00:00Z")
    for event in events:
        event_id = event["id"]
        client.delete_event(event_id)
        print(f"Deleted: {event.get('summary')} ({event_id})")
    print(f"Purge complete — {len(events)} event(s) deleted")


def run_live() -> None:
    from integrations.sheets_client import SheetsClient
    from integrations.gmail_client import GmailClient
    from integrations.calendar_client import CalendarClient
    from agents.release_calendar import run

    sheets = SheetsClient()
    gmail = GmailClient()
    calendar = CalendarClient()
    run(sheets=sheets, gmail=gmail, calendar=calendar, dry_run=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual test for CalendarClient.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--auth", action="store_true", help="Verify calendar auth and list upcoming events.")
    group.add_argument("--create", action="store_true", help="Create a test event for tomorrow.")
    group.add_argument("--delete", metavar="EVENT_ID", help="Delete the event with the given ID.")
    group.add_argument("--live", action="store_true", help="Full live run of release_calendar with real clients.")
    group.add_argument("--purge", action="store_true", help="Delete all calendar events between 2020 and 2030.")
    args = parser.parse_args()

    if args.auth:
        run_auth()
    elif args.create:
        run_create()
    elif args.delete:
        run_delete(args.delete)
    elif args.live:
        run_live()
    elif args.purge:
        run_purge()


if __name__ == "__main__":
    main()
