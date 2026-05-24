"""Draft approval agent. Polls email_log for pending approvals, checks approver replies, and sends approved drafts."""

import os

from integrations.gmail_client import GmailClient
from integrations.sheets_client import SHEET_EMAIL_LOG
from integrations.utils import _extract_email

APPROVER_EMAILS = [e.strip() for e in os.getenv("APPROVER_EMAILS", "").split(",") if e.strip()]


def run(gmail=None, sheets=None) -> None:
    print("\n" + "=" * 60)
    print("[draft_approval] Run started")
    print("=" * 60)

    if gmail is None:
        gmail = GmailClient()

    rows = sheets.get_rows(SHEET_EMAIL_LOG)
    pending = [
        r for r in rows
        if str(r.get("notification_sent", "")).strip().upper() == "TRUE"
        and str(r.get("aprovado", "")).strip().upper() == "FALSE"
        and str(r.get("enviado", "")).strip().upper() == "FALSE"
    ]

    if not pending:
        print("[draft_approval] No pending approvals found.\n")
        return

    print(f"[draft_approval] {len(pending)} pending approval(s) found.\n")

    for row in pending:
        try:
            remetente = str(row.get("remetente", "")).strip()
            assunto = str(row.get("assunto", "")).strip()
            rascunho = str(row.get("rascunho", "")).strip()
            notification_thread_id = str(row.get("notification_thread_id", "")).strip()

            replies = gmail.get_replies_to_thread(notification_thread_id)

            approver_replies = [
                r for r in replies
                if _extract_email(r.get("from", "")).lower() in {e.lower() for e in APPROVER_EMAILS}
            ]

            approved = any(
                "aprovado" in str(r.get("body", "")).strip().lower()
                for r in approver_replies
            )

            if approved:
                sent = gmail.send_email(to=remetente, subject=assunto, body=rascunho)

                if sent:
                    row_number = row["_row_index"]
                    sheets.update_cell(SHEET_EMAIL_LOG, row_number, "aprovado", "TRUE")
                    sheets.update_cell(SHEET_EMAIL_LOG, row_number, "enviado", "TRUE")
                    print(f"[draft_approval] SENT → {remetente} | assunto: {assunto}")
                else:
                    print(f"[draft_approval] SEND FAILED — sheet not updated → {remetente} | assunto: {assunto}")
            else:
                print(f"[draft_approval] Aguardando aprovação → {remetente} | assunto: {assunto}")

        except Exception as e:
            print(f"[draft_approval] ERROR ({row.get('remetente', '')} — {row.get('assunto', '')}): {e}")

    print("[draft_approval] Run complete.\n")
