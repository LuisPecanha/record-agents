"""Google Calendar API client. No business logic."""

import logging
import os

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarClient:
    def __init__(self):
        creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "balters_sheets_service_account.json")
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID")

        if not calendar_id:
            raise EnvironmentError("GOOGLE_CALENDAR_ID not found in environment.")

        credentials = Credentials.from_service_account_file(creds_path, scopes=_SCOPES)
        self.service = build("calendar", "v3", credentials=credentials)
        self.calendar_id = calendar_id

    def create_event(self, summary: str, date: str, description: str) -> str:
        event = {
            "summary": summary,
            "description": description,
            "start": {"date": date},
            "end": {"date": date},
        }
        try:
            created = self.service.events().insert(calendarId=self.calendar_id, body=event).execute()
            return created["id"]
        except Exception as e:
            logger.error("Calendar API create_event failed | calendar_id=%s | summary=%r | date=%s | error=%s", self.calendar_id, summary, date, e)
            raise RuntimeError(f"create_event failed for {summary!r} on {date}: {e}") from e

    def delete_event(self, event_id: str) -> None:
        try:
            self.service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()
        except Exception as e:
            logger.error("Calendar API delete_event failed | calendar_id=%s | event_id=%s | error=%s", self.calendar_id, event_id, e)
            raise RuntimeError(f"delete_event failed for event_id={event_id!r}: {e}") from e

    def list_events(self, time_min: str, time_max: str) -> list:
        response = (
            self.service.events()
            .list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return response.get("items", [])
