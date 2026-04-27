"""Email triage agent. Reads the Balters inbox, uses Claude to classify each email as DEMO / IMPRENSA / PARCERIA / BOOKING / OUTRO, and creates a draft reply in Gmail."""

import os
import re
from datetime import datetime, timezone

import anthropic

from integrations.gmail_client import GmailClient
from prompts.prompts import EMAIL_TRIAGE_PROMPT

_BODY_LIMIT = 3000


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


def _extract_email(from_field: str) -> str:
    match = re.search(r"<(.+?)>", from_field)
    if match:
        return match.group(1).strip()
    return from_field.strip()


def _reply_subject(subject: str) -> str:
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"


def run(gmail=None, sheets=None, claude=None, dry_run: bool = False) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"\n{'='*60}")
    print(f"[email_triage] Run started at {timestamp} | mode: {mode}")
    print(f"{'='*60}")

    if gmail is None:
        gmail = GmailClient()

    if claude is None:
        claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    if sheets is None:
        print("[email_triage] sheets=None — Google Sheets logging skipped for this phase.")

    messages = gmail.get_unread_messages()
    print(f"[email_triage] {len(messages)} unread message(s) to process.\n")

    _skip_patterns = ("no-reply", "noreply", "accounts.google.com", "googlecommunityteam")

    for msg in messages:
        from_lower = msg.get("from", "").lower()
        if any(pattern in from_lower for pattern in _skip_patterns):
            print(f"[email_triage] Skipping automated sender: {msg['from']}")
            gmail.mark_as_read(msg["id"])
            continue

        error_log = ""
        classification = ""
        draft_created = False

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
            classification, draft = _parse_response(raw_text)

            print(f"[email_triage] From    : {msg['from']}")
            print(f"[email_triage] Subject : {msg['subject']}")
            print(f"[email_triage] Class   : {classification}")

            if dry_run:
                print(f"[email_triage] --- DRAFT (dry run) ---\n{draft}\n")
            else:
                to_address = _extract_email(msg["from"])
                subject = _reply_subject(msg["subject"])

                draft_created = gmail.create_draft(
                    to=to_address,
                    subject=subject,
                    body=draft,
                    thread_id=msg.get("thread_id"),
                )
                gmail.mark_as_read(msg["id"])

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
        print()

    print(f"[email_triage] Run complete.\n")
