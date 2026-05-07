"""Google Sheets API client. No business logic."""

import os

import gspread
from google.oauth2.service_account import Credentials

SHEET_LANCAMENTOS = "lancamentos"
SHEET_DEADLINES = "deadlines"
SHEET_EMAIL_LOG = "email_log"
SHEET_DEMOS = "demos"

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


class SheetsClient:
    def __init__(self):
        creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "balters_sheets_service_account.json")
        spreadsheet_id = os.getenv("GOOGLE_SHEETS_ID_RELEASES")

        if not spreadsheet_id:
            raise EnvironmentError("GOOGLE_SHEETS_ID_RELEASES not found in environment.")

        creds = Credentials.from_service_account_file(creds_path, scopes=_SCOPES)
        client = gspread.authorize(creds)
        self._spreadsheet = client.open_by_key(spreadsheet_id)

        print(f"[SheetsClient] Connected to spreadsheet: {self._spreadsheet.title}")

    def _worksheet(self, sheet_name: str) -> gspread.Worksheet:
        available = [ws.title for ws in self._spreadsheet.worksheets()]
        for ws in self._spreadsheet.worksheets():
            if ws.title == sheet_name:
                return ws
        raise ValueError(
            f"Worksheet '{sheet_name}' not found. "
            f"Available tabs: {available}"
        )

    def get_rows(self, sheet_name: str) -> list[dict]:
        ws = self._worksheet(sheet_name)
        records = ws.get_all_records()
        return [{**row, "_row_index": i + 2} for i, row in enumerate(records)]

    def append_row(self, sheet_name: str, row: dict) -> None:
        ws = self._worksheet(sheet_name)
        headers = ws.row_values(1)
        values = [row.get(h, "") for h in headers]
        ws.append_row(values, value_input_option="USER_ENTERED")

    def update_cell(self, sheet_name: str, row_index: int, col_name: str, value: str) -> None:
        ws = self._worksheet(sheet_name)
        headers = ws.row_values(1)
        if col_name not in headers:
            raise ValueError(
                f"Column '{col_name}' not found in '{sheet_name}'. "
                f"Available columns: {headers}"
            )
        col_index = headers.index(col_name) + 1
        ws.update_cell(row_index, col_index, value)
