"""Manual test for the press kit agent."""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

import anthropic
from integrations.sheets_client import SheetsClient, SHEET_LANCAMENTOS
from integrations.gmail_client import GmailClient
from prompts.prompts import PRESS_KIT_PROMPT

MOCK_RELEASE = {
    "_row_index": 1,
    "nome_artista": "IV_C",
    "titulo_track": "Xablau",
    "genero": "House",
    "data_lancamento": "28/06/2025",
    "descricao": "Track inspirada em sets noturnos de clube, com bumbo profundo e synths melancólicos",
    "link_track": "",
    "link_perfil": "",
}


def _build_release_data(row: dict) -> str:
    fields = [
        ("Artista", row.get("nome_artista", "")),
        ("Título", row.get("titulo_track", "")),
        ("Gênero", row.get("genero", "")),
        ("Data de lançamento", row.get("data_lancamento", "")),
        ("Descrição", row.get("descricao", "")),
        ("Link da track", row.get("link_track", "")),
        ("Link do perfil", row.get("link_perfil", "")),
    ]
    return "\n".join(f"{label}: {value}" for label, value in fields if str(value).strip())


def _parse_blocks(text: str) -> tuple[str, str, str]:
    blurb = ""
    release_notes = ""
    social_caption = ""
    parts = text.split("===")
    current = None

    for part in parts:
        stripped = part.strip()
        if stripped == "PRESS KIT BLURB":
            current = "blurb"
        elif stripped == "RELEASE NOTES":
            current = "release_notes"
        elif stripped == "SOCIAL CAPTION":
            current = "social_caption"
        elif current == "blurb":
            blurb = stripped
            current = None
        elif current == "release_notes":
            release_notes = stripped
            current = None
        elif current == "social_caption":
            social_caption = stripped
            current = None

    return blurb, release_notes, social_caption


def _print_blocks(row: dict, blurb: str, release_notes: str, social_caption: str) -> None:
    nome = row.get("nome_artista", "")
    titulo = row.get("titulo_track", "")
    print(f"\n{'='*60}")
    print(f"{nome} — {titulo}")
    print(f"{'='*60}")
    print("PRESS KIT BLURB")
    print("-" * 40)
    print(blurb)
    print("\nRELEASE NOTES")
    print("-" * 40)
    print(release_notes)
    print("\nSOCIAL CAPTION")
    print("-" * 40)
    print(social_caption)
    print()


def _generate(row: dict, claude) -> tuple[str, str, str]:
    release_data = _build_release_data(row)
    response = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": PRESS_KIT_PROMPT.format(release_data=release_data)}],
    )
    return _parse_blocks(response.content[0].text)  # type: ignore[union-attr]


def run_mock() -> None:
    print("Mode: MOCK — hardcoded release, real Claude, no Sheets or email.\n")
    claude = anthropic.Anthropic()
    blurb, release_notes, social_caption = _generate(MOCK_RELEASE, claude)
    _print_blocks(MOCK_RELEASE, blurb, release_notes, social_caption)


def run_dry() -> None:
    print("Mode: DRY RUN — real Sheets rows, real Claude, no writes or email.\n")

    try:
        sheets = SheetsClient()
        claude = anthropic.Anthropic()
    except Exception as e:
        print(f"Client init failed: {e}")
        sys.exit(1)

    rows = sheets.get_rows(SHEET_LANCAMENTOS)
    pending = [
        r for r in rows
        if str(r.get("nome_artista", "")).strip()
        and str(r.get("processado_presskit", "")).strip().upper() != "TRUE"
    ]

    print(f"{len(pending)} unprocessed release(s) found.")

    if not pending:
        print("Nothing to process.")
        return

    for row in pending:
        try:
            blurb, release_notes, social_caption = _generate(row, claude)
            _print_blocks(row, blurb, release_notes, social_caption)
        except Exception as e:
            print(f"ERROR on row {row.get('_row_index')}: {e}")


def run_live() -> None:
    print("Mode: LIVE — processes first unprocessed row end to end.\n")

    try:
        sheets = SheetsClient()
        gmail = GmailClient()
        claude = anthropic.Anthropic()
    except Exception as e:
        print(f"Client init failed: {e}")
        sys.exit(1)

    rows = sheets.get_rows(SHEET_LANCAMENTOS)
    pending = [
        r for r in rows
        if str(r.get("nome_artista", "")).strip()
        and str(r.get("processado_presskit", "")).strip().upper() != "TRUE"
    ]

    if not pending:
        print("No unprocessed releases found.")
        return

    row = pending[0]
    row_number = row["_row_index"]
    nome_artista = str(row.get("nome_artista", "")).strip()
    titulo_track = str(row.get("titulo_track", "")).strip()

    print(f"Processing row {row_number}: {nome_artista} — {titulo_track}\n")

    blurb, release_notes, social_caption = _generate(row, claude)
    _print_blocks(row, blurb, release_notes, social_caption)

    sheets.update_cell(SHEET_LANCAMENTOS, row_number, "presskit_blurb", blurb)
    sheets.update_cell(SHEET_LANCAMENTOS, row_number, "release_notes", release_notes)
    sheets.update_cell(SHEET_LANCAMENTOS, row_number, "social_caption", social_caption)
    print(f"Sheet updated for row {row_number}.")

    email_guilherme = os.getenv("EMAIL_GUILHERME")
    if email_guilherme:
        subject = f"Press Kit gerado — {titulo_track} · {nome_artista}"
        body = (
            f"Olá Guilherme,\n\n"
            f"O press kit abaixo foi gerado automaticamente e aguarda revisão.\n\n"
            f"{'='*60}\n"
            f"PRESS KIT BLURB\n"
            f"{'='*60}\n"
            f"{blurb}\n\n"
            f"{'='*60}\n"
            f"RELEASE NOTES\n"
            f"{'='*60}\n"
            f"{release_notes}\n\n"
            f"{'='*60}\n"
            f"SOCIAL CAPTION\n"
            f"{'='*60}\n"
            f"{social_caption}\n\n"
            f"Equipe Balters Records"
        )
        sent = gmail.send_email(to=email_guilherme, subject=subject, body=body)
        print(f"Email {'sent' if sent else 'FAILED'} → {email_guilherme}")
    else:
        print("EMAIL_GUILHERME not set — skipping email.")

    sheets.update_cell(SHEET_LANCAMENTOS, row_number, "processado_presskit", True)
    print(f"Row {row_number} marked as processado_presskit=True.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual test for the press kit agent.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--mock", action="store_true", help="Hardcoded release, real Claude, no external writes.")
    group.add_argument("--dry-run", action="store_true", help="Real Sheets rows, real Claude, no writes or email.")
    group.add_argument("--live", action="store_true", help="Processes first unprocessed row end to end.")
    args = parser.parse_args()

    if args.mock:
        run_mock()
    elif args.dry_run:
        run_dry()
    elif args.live:
        run_live()


if __name__ == "__main__":
    main()
