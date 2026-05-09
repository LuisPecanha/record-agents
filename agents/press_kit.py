"""Press kit agent. Reads release info from Google Sheets, uses Claude to generate a press release, artist bio, platform description and social media captions."""

import os

from integrations.sheets_client import SHEET_LANCAMENTOS
from prompts.prompts import PRESS_KIT_PROMPT


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


def run(sheets=None, gmail=None, claude=None) -> None:
    print("\n" + "=" * 60)
    print("[press_kit] Run started")
    print("=" * 60)

    email_guilherme = os.getenv("EMAIL_GUILHERME")

    rows = sheets.get_rows(SHEET_LANCAMENTOS)
    pending = [
        r for r in rows
        if str(r.get("nome_artista", "")).strip()
        and str(r.get("processado_presskit", "")).strip().upper() != "TRUE"
    ]
    print(f"[press_kit] {len(pending)} unprocessed release(s) found.\n")

    for row in pending:
        row_number = row["_row_index"]
        nome_artista = str(row.get("nome_artista", "")).strip()
        titulo_track = str(row.get("titulo_track", "")).strip()

        print(f"[press_kit] Processing row {row_number}: {nome_artista} — {titulo_track}")

        try:
            release_data = _build_release_data(row)

            response = claude.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2000,
                messages=[{"role": "user", "content": PRESS_KIT_PROMPT.format(release_data=release_data)}],
            )

            blurb, release_notes, social_caption = _parse_blocks(response.content[0].text)  # type: ignore[union-attr]
            print(f"[press_kit] Claude response parsed — blurb: {len(blurb)} chars, notes: {len(release_notes)} chars, caption: {len(social_caption)} chars")

            sheets.update_cell(SHEET_LANCAMENTOS, row_number, "presskit_blurb", blurb)
            sheets.update_cell(SHEET_LANCAMENTOS, row_number, "release_notes", release_notes)
            sheets.update_cell(SHEET_LANCAMENTOS, row_number, "social_caption", social_caption)
            print(f"[press_kit] Sheet updated for row {row_number}")

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
                print(f"[press_kit] Email {'sent' if sent else 'FAILED'} → {email_guilherme}")
            else:
                print("[press_kit] EMAIL_GUILHERME not set — skipping email.")

            sheets.update_cell(SHEET_LANCAMENTOS, row_number, "processado_presskit", True)
            print(f"[press_kit] Row {row_number} marked as processado_presskit=True\n")

        except Exception as e:
            print(f"[press_kit] ERROR on row {row_number} ({nome_artista} — {titulo_track}): {e}\n")

    print("[press_kit] Run complete.\n")
