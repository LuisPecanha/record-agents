"""Manual test for the release calendar agent."""

import argparse
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()


def run_dry():
    print("Mode: DRY RUN — reads from Sheets, no writes, no emails.\n")
    from integrations.sheets_client import SheetsClient
    from integrations.gmail_client import GmailClient
    from agents import release_calendar

    try:
        sheets = SheetsClient()
        gmail = GmailClient()
    except Exception as e:
        print(f"Client init failed: {e}")
        sys.exit(1)

    release_calendar.run(sheets=sheets, gmail=gmail, dry_run=True)


def run_live():
    print("Mode: LIVE — will write to Sheets and send real emails.\n")
    print("WARNING: This will append a test row to the 'lancamentos' tab")
    print("and trigger the full release calendar pipeline including emails.")
    confirm = input("\nType 'yes' to proceed: ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        sys.exit(0)

    from integrations.sheets_client import SheetsClient, SHEET_LANCAMENTOS
    from integrations.gmail_client import GmailClient
    from agents import release_calendar

    try:
        sheets = SheetsClient()
        gmail = GmailClient()
    except Exception as e:
        print(f"Client init failed: {e}")
        sys.exit(1)

    release_date = (datetime.now(timezone.utc) + timedelta(days=60)).strftime("%d/%m/%Y")

    test_row = {
        "nome_artista": "TEST ARTIST — IGNORE",
        "titulo_track": "Test Track Phase 2 Validation",
        "data_lancamento": release_date,
        "responsado_master": "Blumel",
        "observacoes": "Lançamento fictício criado pelo script de teste",
        "processado": "N",
    }

    print(f"\nAppending test row to 'lancamentos': {test_row}\n")
    try:
        sheets.append_row(SHEET_LANCAMENTOS, test_row)
    except Exception as e:
        print(f"Failed to append test row: {e}")
        sys.exit(1)

    release_calendar.run(sheets=sheets, gmail=gmail, dry_run=False)


def main():
    parser = argparse.ArgumentParser(description="Manual test for the release calendar agent.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Read from Sheets, no writes or emails.")
    group.add_argument("--live", action="store_true", help="Append test row and run the full pipeline.")
    args = parser.parse_args()

    if args.dry_run:
        run_dry()
    elif args.live:
        run_live()


if __name__ == "__main__":
    main()
