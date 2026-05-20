"""Release calendar agent. Reads new release submissions from Google Sheets, calculates 8 retroactive deadlines from the release date, creates events in Google Calendar and notifies the team."""

import os
from datetime import datetime, timedelta

from integrations.sheets_client import SHEET_LANCAMENTOS, SHEET_DEADLINES

_DEADLINES = [
    ("Aprovação final da track", -42),
    ("Entrega para masterização", -35),
    ("Master aprovada", -28),
    ("Arte do single", -21),
    ("Entrega para distribuição", -14),
    ("Envio de promos para DJs", -14),
    ("Campanha de pré-save ativa", -7),
    ("Posts agendados nas redes", -3),
]

_ETAPA_EMOJI = {
    "Aprovação final da track": "🎧",
    "Entrega para masterização": "🎚️",
    "Master aprovada": "✅",
    "Arte do single": "🎨",
    "Entrega para distribuição": "📦",
    "Envio de promos para DJs": "📢",
    "Campanha de pré-save ativa": "🔗",
    "Posts agendados nas redes": "📱",
}

_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d")


def _parse_date(value: str) -> datetime:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: '{value}'. Expected DD/MM/YYYY or YYYY-MM-DD.")


def _format_date(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y")


def run(sheets=None, gmail=None, calendar=None, dry_run: bool = False) -> None:
    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"\n{'='*60}")
    print(f"[release_calendar] Run started | mode: {mode}")
    print(f"{'='*60}")

    email_guilherme = os.getenv("EMAIL_GUILHERME")
    email_luis = os.getenv("EMAIL_LUIS")
    email_equipe = os.getenv("EMAIL_EQUIPE")

    rows = sheets.get_rows(SHEET_LANCAMENTOS)
    pending = [
        r for r in rows
        if (r.get("processado") is False or str(r.get("processado", "")).strip().upper() == "FALSE")
        and str(r.get("nome_artista", "")).strip()
    ]
    print(f"[release_calendar] {len(pending)} unprocessed release(s) found.\n")

    for release in pending:
        row_index = release["_row_index"]
        artist = release.get("nome_artista", "Unknown")
        track = release.get("titulo_track", "Unknown")
        raw_date = release.get("data_lancamento", "")

        print(f"[release_calendar] Processing: {artist} — {track} (row {row_index})")

        try:
            release_date = _parse_date(raw_date)
        except ValueError as e:
            print(f"[release_calendar] Skipping row {row_index}: {e}")
            continue

        try:
            deadlines = [
                {"etapa": stage, "deadline": _format_date(release_date + timedelta(days=offset)), "artista": artist, "titulo": track}
                for stage, offset in _DEADLINES
            ]

            for dl in deadlines:
                emoji = _ETAPA_EMOJI.get(dl["etapa"], "📅")
                summary = f"[{emoji} {dl['etapa']}] {track} — {artist}"
                description = f"Responsável: {dl.get('responsavel', '')}\nLançamento: {_format_date(release_date)}"
                date_iso = datetime.strptime(dl["deadline"], "%d/%m/%Y").strftime("%Y-%m-%d")

                if not dry_run and calendar is not None:
                    try:
                        event_id = calendar.create_event(summary=summary, date=date_iso, description=description)
                        dl["calendar_event_id"] = event_id
                        print(f"[release_calendar] Calendar event created: {summary} ({event_id})")
                    except Exception as cal_err:
                        print(f"[release_calendar] Calendar event FAILED for '{dl['etapa']}': {cal_err}")
                        dl["calendar_event_id"] = ""
                else:
                    dl["calendar_event_id"] = ""
                    if dry_run:
                        print(f"[release_calendar] [DRY RUN] Would create calendar event: {summary}")

                if dry_run:
                    print(f"[release_calendar] [DRY RUN] Would append deadline: {dl['etapa']} — {dl['deadline']}")
                else:
                    sheets.append_row(SHEET_DEADLINES, dl)
                    print(f"[release_calendar] Deadline written: {dl['etapa']} — {dl['deadline']}")

            arte_dl = next(d for d in deadlines if d["etapa"] == "Arte do single")
            entrega_dl = next(d for d in deadlines if d["etapa"] == "Entrega para distribuição")

            summary_lines = "\n".join(f"  {d['etapa']}: {d['deadline']}" for d in deadlines)
            summary_body = (
                f"Novo lançamento processado: {artist} — {track}\n"
                f"Data de lançamento: {_format_date(release_date)}\n\n"
                f"Deadlines calculados:\n{summary_lines}"
            )

            notifications = [
                (
                    email_guilherme,
                    f"[Balters] Arte do single — {artist}",
                    f"Olá Guilherme,\n\nO deadline para a arte do single de '{track}' ({artist}) é {arte_dl['deadline']}.\n\nEquipe Balters Records",
                ),
                (
                    email_luis,
                    f"[Balters] Entrega para distribuição — {artist}",
                    f"Olá Luís,\n\nO deadline para entrega para distribuição de '{track}' ({artist}) é {entrega_dl['deadline']}.\n\nEquipe Balters Records",
                ),
                (
                    email_equipe,
                    f"[Balters] Deadlines calculados — {artist} — {track}",
                    summary_body,
                ),
            ]

            for to_addr, subject, body in notifications:
                if not to_addr:
                    print(f"[release_calendar] Skipping notification — recipient env var not set (subject: {subject})")
                    continue
                if dry_run:
                    print(f"[release_calendar] [DRY RUN] Would send email to {to_addr}: {subject}")
                else:
                    sent = gmail.send_email(to=to_addr, subject=subject, body=body)
                    print(f"[release_calendar] Email {'sent' if sent else 'FAILED'} → {to_addr}: {subject}")

            if dry_run:
                print(f"[release_calendar] [DRY RUN] Would mark row {row_index} as processado=S")
            else:
                sheets.update_cell(SHEET_LANCAMENTOS, row_index, "processado", True)
                print(f"[release_calendar] Row {row_index} marked as processado=S")

        except Exception as e:
            print(f"[release_calendar] ERROR on row {row_index} ({artist} — {track}): {e}")

        print()

    print("[release_calendar] Run complete.\n")
