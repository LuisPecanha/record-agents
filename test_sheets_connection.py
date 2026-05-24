"""Manual test: verifies SheetsClient can connect and read all expected tabs."""

import sys
from dotenv import load_dotenv

load_dotenv()

from integrations.sheets_client import SheetsClient, SHEET_LANCAMENTOS, SHEET_DEADLINES, SHEET_EMAIL_LOG

failed = False

try:
    client = SheetsClient()
except Exception as e:
    print(f"✗ SheetsClient init failed: {e}")
    sys.exit(1)

for tab, anchor in [
    (SHEET_LANCAMENTOS, "nome_artista"),
    (SHEET_DEADLINES, "artista"),
    (SHEET_EMAIL_LOG, "remetente"),
]:
    try:
        rows = client.get_rows(tab, anchor=anchor)
        print(f"✓ {tab}: {len(rows)} row(s)")
    except Exception as e:
        print(f"✗ {tab}: {e}")
        failed = True

if failed:
    sys.exit(1)

print("\nAll tabs connected successfully.")
