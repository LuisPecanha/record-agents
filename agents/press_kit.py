"""Press kit agent. Reads release info from Google Sheets, uses Claude to generate a press release, artist bio, platform description and social media captions."""

import os
from datetime import datetime

from integrations.sheets_client import SHEET_LANCAMENTOS
from prompts.prompts import PRESS_KIT_PROMPT

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def _format_file_content(blurb: str, release_notes: str, social_caption: str) -> str:
    sep = "=" * 60
    return (
        f"{sep}\nPRESS KIT BLURB\n{sep}\n{blurb}\n\n"
        f"{sep}\nRELEASE NOTES\n{sep}\n{release_notes}\n\n"
        f"{sep}\nSOCIAL CAPTION\n{sep}\n{social_caption}\n"
    )


def _save_press_kit(filename: str, content: str, year: str, month: str) -> str:
    dir_path = os.path.join(_PROJECT_ROOT, "press_kits", year, month)
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path


def run(sheets=None, gmail=None, claude=None) -> None:
    print("\n" + "=" * 60)
    print("[press_kit] Run started")
    print("=" * 60)

    email_design = os.getenv("EMAIL_DESIGN")

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
        data_lancamento = str(row.get("data_lancamento", "")).strip()

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

            try:
                dt = datetime.strptime(data_lancamento, "%d/%m/%Y")
            except ValueError:
                dt = datetime.strptime(data_lancamento, "%Y-%m-%d")
            year = dt.strftime("%Y")
            month = dt.strftime("%m")

            safe_name = f"{nome_artista}_{titulo_track}_{data_lancamento}".replace(" ", "_").replace("/", "-").lower()
            filename = f"{safe_name}.txt"
            file_content = _format_file_content(blurb, release_notes, social_caption)

            file_path = _save_press_kit(filename, file_content, year, month)
            print(f"[press_kit] File saved: {file_path}")

            if email_design:
                subject = f"Press Kit gerado — {titulo_track} · {nome_artista}"
                body = (
                    f"Olá Guilherme,\n\n"
                    f"O press kit de '{titulo_track}' ({nome_artista}) foi gerado e está anexado a este email para revisão.\n\n"
                    f"Equipe Balters Records"
                )
                sent = gmail.send_email_with_attachment(
                    to=email_design,
                    subject=subject,
                    body=body,
                    attachment_content=file_content,
                    attachment_filename=filename,
                )
                print(f"[press_kit] Email {'sent' if sent else 'FAILED'} → {email_design}")
            else:
                print("[press_kit] EMAIL_DESIGN not set — skipping email.")

            sheets.update_cell(SHEET_LANCAMENTOS, row_number, "processado_presskit", True)
            print(f"[press_kit] Row {row_number} marked as processado_presskit=True\n")

        except Exception as e:
            print(f"[press_kit] ERROR on row {row_number} ({nome_artista} — {titulo_track}): {e}\n")

    print("[press_kit] Run complete.\n")
