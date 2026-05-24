"""Manual test for the deadline_tracking agent."""

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

from automations.deadline_tracking import run_daily, run_weekly  # noqa: E402


class MockSheets:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def get_rows(self, tab: str, anchor: str | None = None) -> list[dict]:
        return self.rows

    def update_cell(self, tab: str, row_index: int, col: str, value: str) -> None:
        self.rows[row_index - 2][col] = value
        print(f"[MOCK SHEETS] update_cell({tab}, row {row_index}, {col} = {value})")


class MockGmail:
    def send_email(self, to: str, subject: str, body: str) -> str:
        print(f"[MOCK GMAIL] send_email(to={to})\n  subject: {subject}\n  body preview: {body[:120]}...")
        return "<mock-message-id@balters.com>"


def _build_mock_rows() -> list[dict]:
    today = date.today()
    return [
        {
            "artista": "DJ Teste", "titulo": "Track A", "etapa": "Arte do single",
            "deadline": (today + timedelta(days=2)).isoformat(),
            "status": "Pendente", "responsavel": "Guilherme", "alerta_enviado": "FALSE",
        },
        {
            "artista": "DJ Teste", "titulo": "Track A", "etapa": "Entrega para distribuição",
            "deadline": (today - timedelta(days=1)).isoformat(),
            "status": "Pendente", "responsavel": "Luis", "alerta_enviado": "FALSE",
        },
        {
            "artista": "DJ Teste", "titulo": "Track A", "etapa": "Envio de promos para DJs",
            "deadline": (today - timedelta(days=5)).isoformat(),
            "status": "Atrasado", "responsavel": "Equipe", "alerta_enviado": "FALSE",
        },
        {
            "artista": "DJ Teste", "titulo": "Track A", "etapa": "Campanha de pré-save ativa",
            "deadline": (today + timedelta(days=10)).isoformat(),
            "status": "Pendente", "responsavel": "Guilherme", "alerta_enviado": "FALSE",
        },
        {
            "artista": "DJ Teste", "titulo": "Track A", "etapa": "Posts agendados nas redes",
            "deadline": (today + timedelta(days=17)).isoformat(),
            "status": "Pendente", "responsavel": "Guilherme", "alerta_enviado": "FALSE",
        },
    ]


def run_mock() -> None:
    print("=" * 60)
    print("MODE: MOCK — hardcoded rows, fake Sheets/Gmail, no real calls.")
    print("=" * 60 + "\n")

    rows = _build_mock_rows()
    sheets = MockSheets(rows)
    gmail = MockGmail()

    print("--- run_daily ---\n")
    run_daily(sheets, gmail)

    print("\n" + "=" * 60)
    print("Final row state after run_daily:")
    print("=" * 60)
    for row in rows:
        print(f"  {row['etapa']:35s} deadline={row['deadline']}  alerta_enviado={row['alerta_enviado']}")

    print("\n" + "=" * 60)
    print("--- run_weekly ---\n")
    run_weekly(MockSheets(rows), MockGmail())


def run_dry() -> None:
    print("=" * 60)
    print("MODE: DRY-RUN — real Sheets, no writes or emails.")
    print("=" * 60 + "\n")

    try:
        from integrations.sheets_client import SheetsClient
        from integrations.gmail_client import GmailClient
        sheets = SheetsClient()
    except Exception as e:
        print(f"Client init failed: {e}")
        sys.exit(1)

    rows = sheets.get_rows("deadlines", anchor="artista")
    today = date.today()
    week_end = today + timedelta(days=7)

    print(f"Fetched {len(rows)} row(s) from deadlines tab.\n")

    overdue_rows: list[dict] = []
    upcoming_rows: list[dict] = []
    completed_rows: list[dict] = []

    for row in rows:
        try:
            deadline_date = date.fromisoformat(row["deadline"])
        except (ValueError, KeyError):
            print(f"[DRY-RUN] Skipping row with unparseable deadline: {row}")
            continue

        if row["status"] == "Concluído":
            action = "no action (Concluído)"
            completed_rows.append(row)
        elif row["status"] == "Atrasado":
            action = "cascade would fire"
        else:
            days_until = (deadline_date - today).days
            if 0 <= days_until <= 3 and row["alerta_enviado"] == "FALSE":
                action = "approaching alert would fire"
            elif deadline_date < today and row["alerta_enviado"] == "FALSE":
                action = "overdue alert would fire"
                overdue_rows.append(row)
            else:
                action = "no action"

            if row["status"] == "Pendente" and today <= deadline_date <= week_end:
                upcoming_rows.append(row)

        print(
            f"[DRY-RUN] {row['artista']} - {row['titulo']} | {row['etapa']} | "
            f"deadline: {row['deadline']} | status: {row['status']} | "
            f"alerta_enviado: {row['alerta_enviado']} → ACTION: {action}"
        )

    print("\n" + "=" * 60)
    print("Weekly summary dry-run:")
    print("=" * 60)

    print("\n🔴 ETAPAS VENCIDAS:")
    if overdue_rows:
        for r in overdue_rows:
            print(f"  {r['artista']} - {r['titulo']} | {r['etapa']} ({r['deadline']})")
    else:
        print("  (nenhuma)")

    print("\n🟡 PRÓXIMOS PRAZOS (7 dias):")
    if upcoming_rows:
        for r in upcoming_rows:
            print(f"  {r['artista']} - {r['titulo']} | {r['etapa']} ({r['deadline']})")
    else:
        print("  (nenhuma)")

    print("\n✅ ETAPAS CONCLUÍDAS:")
    if completed_rows:
        for r in completed_rows:
            print(f"  {r['artista']} - {r['titulo']} | {r['etapa']} ({r['deadline']})")
    else:
        print("  (nenhuma)")


def run_live() -> None:
    print("=" * 60)
    print("MODE: LIVE — real run_daily with real clients.")
    print("=" * 60 + "\n")

    try:
        from integrations.sheets_client import SheetsClient
        from integrations.gmail_client import GmailClient
        sheets = SheetsClient()
        gmail = GmailClient()
    except Exception as e:
        print(f"Client init failed: {e}")
        sys.exit(1)

    rows = sheets.get_rows("deadlines", anchor="artista")
    today = date.today()

    eligible = None
    for row in rows:
        if row["status"] != "Pendente" or row["alerta_enviado"] != "FALSE":
            continue
        try:
            deadline_date = date.fromisoformat(row["deadline"])
        except (ValueError, KeyError):
            continue
        days_until = (deadline_date - today).days
        if 0 <= days_until <= 3 or deadline_date < today:
            eligible = row
            break

    if eligible is None:
        print("No eligible row found for live test.")
        sys.exit(0)

    print("Row that will be processed:")
    print(f"  artista      : {eligible['artista']}")
    print(f"  titulo       : {eligible['titulo']}")
    print(f"  etapa        : {eligible['etapa']}")
    print(f"  deadline     : {eligible['deadline']}")
    print(f"  status       : {eligible['status']}")
    print(f"  alerta_enviado: {eligible['alerta_enviado']}")
    print()

    run_daily(sheets, gmail)
    print("Live run complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual test for the deadline_tracking agent.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--mock", action="store_true", help="Hardcoded rows, fake clients, no real calls.")
    group.add_argument("--dry-run", action="store_true", help="Real Sheets, evaluate actions without writing.")
    group.add_argument("--live", action="store_true", help="Full run_daily with real clients.")
    args = parser.parse_args()

    if args.mock:
        run_mock()
    elif args.dry_run:
        run_dry()
    elif args.live:
        run_live()


if __name__ == "__main__":
    main()
