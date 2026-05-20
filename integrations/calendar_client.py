"""Google Calendar API client. No business logic."""

import os
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

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
        created = self.service.events().insert(calendarId=self.calendar_id, body=event).execute()
        return created["id"]

    def delete_event(self, event_id: str) -> None:
        self.service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()

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
