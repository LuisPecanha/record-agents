"""Manual test for the draft_approval agent."""

import os
import re
import sys
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=env_path)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agents.draft_approval as draft_approval
from integrations.gmail_client import GmailClient
from integrations.sheets_client import SheetsClient, SHEET_EMAIL_LOG

MOCK_ROW = {
    "_row_index": 2,
    "remetente": "artist@example.com",
    "assunto": "Re: Demo",
    "rascunho": "Olá, obrigado...",
    "notification_thread_id": "<fake-message-id@balters.com>",
    "notification_sent": "TRUE",
    "aprovado": "FALSE",
    "enviado": "FALSE",
}

MOCK_REPLY = {"from": "matias@example.com", "body": "APROVADO"}


def _extract_email(from_field: str) -> str:
    match = re.search(r"<(.+?)>", from_field)
    if match:
        return match.group(1).strip()
    return from_field.strip()


def run_mock() -> None:
    print("[test_draft_approval] Mode: MOCK — fake data, no network calls.\n")

    draft_approval.APPROVER_EMAILS = ["matias@example.com"]

    approver_emails_lower = {e.lower() for e in draft_approval.APPROVER_EMAILS}
    sender = _extract_email(MOCK_REPLY["from"]).lower()
    sender_qualifies = sender in approver_emails_lower
    body_qualifies = "aprovado" in MOCK_REPLY["body"].strip().lower()

    print(f"[test_draft_approval] Sender '{MOCK_REPLY['from']}' in APPROVER_EMAILS: {sender_qualifies}")
    print(f"[test_draft_approval] Body contains 'APROVADO': {body_qualifies}")

    if sender_qualifies and body_qualifies:
        print("[test_draft_approval] PASS — logic would approve and send the draft.")
    else:
        print("[test_draft_approval] FAIL — approval condition not met.")


def run_dry() -> None:
    print("[test_draft_approval] Mode: DRY RUN — real clients, no writes.\n")

    try:
        gmail = GmailClient()
        sheets = SheetsClient()
    except Exception as e:
        print(f"[test_draft_approval] Client init failed: {e}")
        sys.exit(1)

    rows = sheets.get_rows(SHEET_EMAIL_LOG, anchor="remetente")
    pending = [
        r for r in rows
        if str(r.get("notification_sent", "")).strip().upper() == "TRUE"
        and str(r.get("aprovado", "")).strip().upper() == "FALSE"
        and str(r.get("enviado", "")).strip().upper() == "FALSE"
    ]

    print(f"[test_draft_approval] {len(pending)} pending approval(s) found in email_log.\n")

    if not pending:
        print("[test_draft_approval] Nothing to check.")
        return

    for row in pending:
        remetente = str(row.get("remetente", "")).strip()
        assunto = str(row.get("assunto", "")).strip()
        thread_id = str(row.get("notification_thread_id", "")).strip()

        print(f"[test_draft_approval] Row {row.get('_row_index')} — {remetente} | {assunto}")
        print(f"[test_draft_approval]   notification_thread_id: {thread_id}")

        replies = gmail.get_replies_to_thread(thread_id)
        print(f"[test_draft_approval]   Replies found: {len(replies)}")

        approver_emails_lower = {e.lower() for e in draft_approval.APPROVER_EMAILS}
        qualifying = [
            r for r in replies
            if _extract_email(r.get("from", "")).lower() in approver_emails_lower
            and "aprovado" in str(r.get("body", "")).strip().lower()
        ]

        if qualifying:
            print(f"[test_draft_approval]   Qualifying approval reply found — would send and mark as enviado.")
        else:
            print(f"[test_draft_approval]   No qualifying reply yet — waiting.")
        print()


def run_live() -> None:
    print("[test_draft_approval] Mode: LIVE")
    print("[test_draft_approval] WARNING: this will send a real email and update Sheets.")
    print("[test_draft_approval] Press Ctrl+C within 5 seconds to abort.\n")

    import time
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        print("\n[test_draft_approval] Aborted.")
        sys.exit(0)

    try:
        gmail = GmailClient()
        sheets = SheetsClient()
    except Exception as e:
        print(f"[test_draft_approval] Client init failed: {e}")
        sys.exit(1)

    draft_approval.run(gmail=gmail, sheets=sheets)


def main() -> None:
    modes = {"--mock", "--dry-run", "--live"}
    args = set(sys.argv[1:])
    matched = args & modes

    if not matched:
        print("Usage: python tests/test_draft_approval.py --mock | --dry-run | --live")
        sys.exit(1)

    mode = matched.pop()
    if mode == "--mock":
        run_mock()
    elif mode == "--dry-run":
        run_dry()
    elif mode == "--live":
        run_live()


if __name__ == "__main__":
    main()
