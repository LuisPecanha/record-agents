# scripts/add_presskit_columns.py
"""
One-time script to add Phase 4 columns to the lancamentos tab.
Run once, then delete or archive.
"""

import os
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

NEW_COLUMNS = [
    "descricao",
    "link_track",
    "link_perfil",
    "presskit_blurb",
    "release_notes",
    "social_caption",
    "processado_presskit",
]

def main():
    creds = Credentials.from_service_account_file(
        os.environ["GOOGLE_SERVICE_ACCOUNT_PATH"], scopes=SCOPES
    )
    client = gspread.authorize(creds)

    sheet = client.open_by_key(os.environ["GOOGLE_SHEETS_ID_RELEASES"])
    ws = sheet.worksheet("lancamentos")

    existing_headers = ws.row_values(1)
    print(f"Existing headers: {existing_headers}")

    cols_to_add = [c for c in NEW_COLUMNS if c not in existing_headers]
    if not cols_to_add:
        print("All columns already exist. Nothing to do.")
        return

    next_col = len(existing_headers) + 1
    for i, col_name in enumerate(cols_to_add):
        col_index = next_col + i
        ws.update_cell(1, col_index, col_name)
        print(f"  Added column '{col_name}' at position {col_index}")

    # Re-fetch headers after update to get correct index
    updated_headers = ws.row_values(1)
    pk_col_index = updated_headers.index("processado_presskit")

    ws.spreadsheet.batch_update({
        "requests": [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": ws.id,
                        "startRowIndex": 1,
                        "endRowIndex": 1000,
                        "startColumnIndex": pk_col_index,
                        "endColumnIndex": pk_col_index + 1,
                    },
                    "cell": {
                        "dataValidation": {
                            "condition": {"type": "BOOLEAN"},
                            "strict": True,
                        }
                    },
                    "fields": "dataValidation",
                }
            }
        ]
    })
    print("Checkbox validation applied to processado_presskit column.")
    print("Done.")

if __name__ == "__main__":
    main()