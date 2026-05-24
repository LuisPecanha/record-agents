"""Email triage agent. Reads the Balters inbox, uses Claude to classify each email as DEMO / IMPRENSA / PARCERIA / BOOKING / OUTRO, and creates a draft reply in Gmail."""

import os
from datetime import datetime, timezone

from integrations.utils import _extract_email
from prompts.prompts import EMAIL_TRIAGE_PROMPT

_BODY_LIMIT = 3000  # caps API input cost and keeps email bodies well within the context window
_SKIP_PATTERNS = ("no-reply", "noreply", "accounts.google.com", "googlecommunityteam")
APPROVER_EMAILS = [e.strip() for e in os.getenv("APPROVER_EMAILS", "").split(",") if e.strip()]


def _parse_response(text: str) -> tuple[str, str]:
    classification = ""
    draft = ""

    for line in text.splitlines():
        if line.startswith("CLASSIFICACAO:"):
            classification = line.removeprefix("CLASSIFICACAO:").strip()
            break

    if "RASCUNHO:" in text:
        draft = text.split("RASCUNHO:", 1)[1].strip()

    return classification, draft


def _reply_subject(subject: str) -> str:
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"


def _build_notification_body(from_field: str, subject: str, classification: str, draft: str) -> str:
    sep = "-" * 60
    return (
        f"Um novo email foi triado e um rascunho de resposta foi criado.\n"
        f"Para aprovar o envio, responda este email com APROVADO.\n"
        f"{sep}\n"
        f"De: {from_field}\n"
        f"Assunto: {subject}\n"
        f"Classificação: {classification}\n"
        f"{sep}\n"
        f"{draft}\n"
        f"{sep}\n"
        f"Responda com APROVADO para autorizar o envio desta resposta."
    )


def _process_message(msg: dict, gmail, sheets, claude, dry_run: bool, timestamp: str) -> None:
    error_log = ""
    classification = ""
    draft_created = False
    notification_sent = False
    notification_thread_id = ""
    draft_body = ""

    try:
        prompt = EMAIL_TRIAGE_PROMPT.format(
            **{**msg, "body": msg["body"][:_BODY_LIMIT]}
        )

        response = claude.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = response.content[0].text
        classification, draft_body = _parse_response(raw_text)

        print(f"[email_triage] From    : {msg['from']}")
        print(f"[email_triage] Subject : {msg['subject']}")
        print(f"[email_triage] Class   : {classification}")

        if dry_run:
            print(f"[email_triage] --- DRAFT (dry run) ---\n{draft_body}\n")
        else:
            to_address = _extract_email(msg["from"])
            subject = _reply_subject(msg["subject"])

            draft_created = gmail.create_draft(
                to=to_address,
                subject=subject,
                body=draft_body,
                thread_id=msg.get("thread_id"),
            )
            gmail.mark_as_read(msg["id"])

            if draft_created and APPROVER_EMAILS:
                notification_subject = f"[APROVACAO PENDENTE] {classification} — {msg['subject']}"
                notification_body = _build_notification_body(
                    from_field=msg["from"],
                    subject=msg["subject"],
                    classification=classification,
                    draft=draft_body,
                )
                notification_thread_id = gmail.send_email(
                    to=", ".join(APPROVER_EMAILS),
                    subject=notification_subject,
                    body=notification_body,
                )
                notification_sent = bool(notification_thread_id)
                print(f"[email_triage] Notification sent | message_id={notification_thread_id}")
            elif draft_created:
                print("[email_triage] WARNING: APPROVER_EMAILS is empty — notification skipped.")

            if sheets is not None and draft_created:
                sheets.append_row("email_log", {
                    "data": timestamp,
                    "remetente": msg.get("from", ""),
                    "assunto": msg.get("subject", ""),
                    "classificacao": classification,
                    "rascunho": draft_body,
                    "notification_sent": "TRUE" if notification_sent else "FALSE",
                    "notification_thread_id": notification_thread_id,
                    "aprovado": "FALSE",
                    "enviado": "FALSE",
                })

    except Exception as e:
        error_log = str(e)
        print(f"[email_triage] ERROR processing message {msg.get('id')}: {e}")

    print(
        f"[email_triage] SHEETS LOG | "
        f"ts={timestamp} | "
        f"from={msg.get('from', '')} | "
        f"subject={msg.get('subject', '')} | "
        f"classification={classification} | "
        f"draft_created={draft_created} | "
        f"error={error_log or 'none'}"
    )


def run(gmail=None, sheets=None, claude=None, dry_run: bool = False) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"\n{'='*60}")
    print(f"[email_triage] Run started at {timestamp} | mode: {mode}")
    print(f"{'='*60}")

    if sheets is None:
        print("[email_triage] sheets=None — Google Sheets logging skipped for this phase.")

    messages = gmail.get_unread_messages()
    print(f"[email_triage] {len(messages)} unread message(s) to process.\n")

    for msg in messages:
        from_lower = msg.get("from", "").lower()
        if any(pattern in from_lower for pattern in _SKIP_PATTERNS):
            print(f"[email_triage] Skipping automated sender: {msg['from']}")
            gmail.mark_as_read(msg["id"])
            continue

        _process_message(msg, gmail, sheets, claude, dry_run, timestamp)
        print()

    print(f"[email_triage] Run complete.\n")
