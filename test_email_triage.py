"""Manual test script for the email triage agent."""

import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


FAKE_MESSAGE = {
    "id": "mock-uid-001",
    "thread_id": "<abc123@mail.gmail.com>",
    "from": "Lucas Ferreira <lucas.ferreira.producer@gmail.com>",
    "subject": "Demo submission - house track",
    "body": (
        "Oi, tudo bem?\n\n"
        "Me chamo Lucas, sou produtor de house music de São Paulo. "
        "Estou mandando um link do meu track mais recente, seria incrível "
        "ter o feedback de vocês da Balters.\n\n"
        "SoundCloud: https://soundcloud.com/lucasferreirasp/balters-demo-2024\n\n"
        "O track é um deep house com influências afro, 124 BPM. "
        "Produzido e mixado por mim no home studio.\n\n"
        "Qualquer feedback já ajuda muito. Obrigado!\n\n"
        "Lucas Ferreira"
    ),
    "date": "Sat, 26 Apr 2026 10:30:00 +0000",
}


class MockGmail:
    def get_unread_messages(self):
        return [FAKE_MESSAGE]

    def create_draft(self, to, subject, body, thread_id=None):
        print("[MockGmail] create_draft called:")
        print(f"  To      : {to}")
        print(f"  Subject : {subject}")
        print(f"  Thread  : {thread_id}")
        print(f"  Body    :\n{body}")
        return True

    def mark_as_read(self, uid):
        print(f"[MockGmail] mark_as_read called for UID: {uid}")
        return True


def run_dry():
    print("Mode: DRY RUN — real Gmail, no writes.\n")
    from agents.email_triage import run
    run(dry_run=True)


def run_gmail_only():
    print("Mode: GMAIL — testing IMAP connection only.\n")
    from integrations.gmail_client import GmailClient
    gmail = GmailClient()
    messages = gmail.get_unread_messages()
    print(f"Unread messages found: {len(messages)}")
    for msg in messages:
        print(f"  [{msg['id']}] {msg['date']} | {msg['from']} | {msg['subject']}")


def run_mock():
    print("Mode: MOCK — fake email, mock Gmail, real Claude.\n")
    from agents.email_triage import run
    run(gmail=MockGmail(), dry_run=False)


def run_live():
    print("Mode: LIVE — real Gmail, real drafts will be created.\n")
    confirm = input("This will create real drafts in Gmail. Type YES to continue: ").strip()
    if confirm != "YES":
        print("Aborted.")
        return
    from agents.email_triage import run
    run(dry_run=False)


def main():
    parser = argparse.ArgumentParser(description="Manual test for the email triage agent.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--gmail", action="store_true", help="Test IMAP connection only.")
    group.add_argument("--mock", action="store_true", help="Run with fake email and mock Gmail.")
    group.add_argument("--live", action="store_true", help="Run live — creates real drafts.")
    args = parser.parse_args()

    if args.gmail:
        run_gmail_only()
    elif args.mock:
        run_mock()
    elif args.live:
        run_live()
    else:
        run_dry()


if __name__ == "__main__":
    main()
