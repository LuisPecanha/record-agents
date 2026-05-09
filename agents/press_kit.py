"""Press kit agent. Reads release info from Google Sheets, uses Claude to generate a press release, artist bio, platform description and social media captions."""

import os
from datetime import datetime

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

from integrations.sheets_client import SHEET_LANCAMENTOS
from prompts.prompts import PRESS_KIT_PROMPT

_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
_PRESS_KIT_ROOT_ID = os.environ.get("GOOGLE_DRIVE_PRESS_KIT_ROOT_ID")


def _drive_service():
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "balters_sheets_service_account.json")
    creds = Credentials.from_service_account_file(creds_path, scopes=_DRIVE_SCOPES)
    return build("drive", "v3", credentials=creds)


def _get_or_create_folder(service, name: str, parent_id: str | None = None) -> str:
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    metadata: dict = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def _upload_press_kit(service, filename: str, content: str, year: str, month: str) -> str:
    root_id = _PRESS_KIT_ROOT_ID
    year_id = _get_or_create_folder(service, year, parent_id=root_id)
    month_id = _get_or_create_folder(service, month, parent_id=year_id)

    metadata = {"name": filename, "parents": [month_id]}
    media = MediaInMemoryUpload(content.encode("utf-8"), mimetype="text/plain")
    file = service.files().create(body=metadata, media_body=media, fields="id,webViewLink").execute()
    return file.get("webViewLink", "")


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

            drive = _drive_service()
            drive_link = _upload_press_kit(drive, filename, file_content, year, month)
            print(f"[press_kit] File uploaded to Drive: {drive_link}")

            if email_guilherme:
                subject = f"Press Kit gerado — {titulo_track} · {nome_artista}"
                body = (
                    f"Olá Guilherme,\n\n"
                    f"O press kit de '{titulo_track}' ({nome_artista}) foi gerado e está pronto para revisão.\n\n"
                    f"Acesse o arquivo no Google Drive:\n{drive_link}\n\n"
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
