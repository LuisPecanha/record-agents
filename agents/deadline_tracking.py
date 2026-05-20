"""Deadline tracking agent. Sends approaching/overdue alerts and cascades delays automatically."""

import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

EMAIL_EQUIPE = os.getenv("EMAIL_EQUIPE")
EMAIL_GUILHERME = os.getenv("EMAIL_GUILHERME")
EMAIL_LUIS = os.getenv("EMAIL_LUIS")
EMAIL_BLUMEL = os.getenv("EMAIL_BLUMEL")

logger = logging.getLogger(__name__)

ETAPA_TO_EMAIL = {
    "Aprovação final da track": EMAIL_EQUIPE,
    "Entrega para masterização": EMAIL_BLUMEL,
    "Master aprovada": EMAIL_BLUMEL,
    "Arte do single": EMAIL_GUILHERME,
    "Entrega para distribuição": EMAIL_LUIS,
    "Envio de promos para DJs": EMAIL_EQUIPE,
    "Campanha de pré-save ativa": EMAIL_GUILHERME,
    "Posts agendados nas redes": EMAIL_GUILHERME,
}

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


def _parse_date(value: str) -> date:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: '{value}'")


def get_responsible(etapa: str) -> str | None:
    return ETAPA_TO_EMAIL.get(etapa) or None


def run_daily(sheets, gmail, calendar=None) -> None:
    """Runs alert logic and cascade logic for all rows in the deadlines tab."""
    rows = sheets.get_rows("deadlines")
    today = date.today()
    cascaded_set: set[tuple[str, str]] = set()

    # Alert logic pass
    for row in rows:
        try:
            deadline_date = _parse_date(row["deadline"])

            if row["status"] == "Concluído":
                continue

            days_until = (deadline_date - today).days
            approaching = (
                0 <= days_until <= 3
                and row["status"] == "Pendente"
                and row["alerta_enviado"] == "FALSE"
            )
            overdue = (
                deadline_date < today
                and row["status"] == "Pendente"
                and row["alerta_enviado"] == "FALSE"
            )

            if approaching:
                recipient = get_responsible(row["etapa"])
                if recipient is None:
                    logger.warning(f"No recipient for etapa '{row['etapa']}' — skipping approaching alert.")
                    continue
                subject = f"Balters — Prazo se aproximando: {row['etapa']} ({row['artista']} - {row['titulo']})"
                body = (
                    f"Olá,\n\n"
                    f"O prazo para a etapa '{row['etapa']}' do lançamento '{row['artista']} - {row['titulo']}' "
                    f"vence em {days_until} dia(s), no dia {row['deadline']}.\n\n"
                    f"Por favor, confirme se está tudo encaminhado.\n\n"
                    f"Balters Records"
                )
                gmail.send_email(recipient, subject, body)
                row_index = sheets.get_rows("deadlines").index(row) + 2
                sheets.update_cell("deadlines", row_index, "alerta_enviado", "TRUE")
                logger.info(f"Approaching alert sent for {row['artista']} - {row['titulo']} / {row['etapa']}")

            if overdue:
                recipient = get_responsible(row["etapa"])
                if recipient is None:
                    logger.warning(f"No recipient for etapa '{row['etapa']}' — skipping overdue alert.")
                    continue
                recipients_str = recipient if recipient == EMAIL_EQUIPE else f"{recipient},{EMAIL_EQUIPE}"
                subject = f"Balters — Prazo VENCIDO: {row['etapa']} ({row['artista']} - {row['titulo']})"
                body = (
                    f"Atenção,\n\n"
                    f"A etapa '{row['etapa']}' do lançamento '{row['artista']} - {row['titulo']}' "
                    f"tinha prazo em {row['deadline']} e está VENCIDA.\n\n"
                    f"Por favor, atualizem o status na planilha e tomem as providências necessárias.\n\n"
                    f"Balters Records"
                )
                gmail.send_email(recipients_str, subject, body)
                row_index = sheets.get_rows("deadlines").index(row) + 2
                sheets.update_cell("deadlines", row_index, "alerta_enviado", "TRUE")
                logger.info(f"Overdue alert sent for {row['artista']} - {row['titulo']} / {row['etapa']}")

        except Exception as e:
            logger.error(f"Error processing alert for row {row}: {e}")
            continue

    # Cascade logic pass
    for row in rows:
        try:
            deadline_date = _parse_date(row["deadline"])

            if row["status"] != "Atrasado":
                continue

            release_key = (row["artista"], row["titulo"])
            if release_key in cascaded_set:
                continue

            delay_days = (today - deadline_date).days
            if delay_days <= 0:
                continue

            all_rows = sheets.get_rows("deadlines")
            downstream = [
                r for r in all_rows
                if r["artista"] == row["artista"]
                and r["titulo"] == row["titulo"]
                and _parse_date(r["deadline"]) > deadline_date
            ]

            if not downstream:
                continue

            changes = []
            for dr in downstream:
                old_date = _parse_date(dr["deadline"])
                new_date = old_date + timedelta(days=delay_days)
                dr_index = all_rows.index(dr) + 2
                sheets.update_cell("deadlines", dr_index, "deadline", new_date.isoformat())
                if dr["alerta_enviado"] == "FALSE":
                    sheets.update_cell("deadlines", dr_index, "alerta_enviado", "FALSE")
                else:
                    logger.debug(
                        f"Skipping alerta_enviado reset for {dr['etapa']} — alert already sent this run"
                    )
                if calendar is not None and dr.get("calendar_event_id"):
                    try:
                        calendar.delete_event(dr["calendar_event_id"])
                        emoji = _ETAPA_EMOJI.get(dr["etapa"], "📅")
                        summary = f"[{emoji} {dr['etapa']}] {dr['titulo']} — {dr['artista']}"
                        description = f"Responsável: {dr.get('responsavel', '')}"
                        new_event_id = calendar.create_event(
                            summary=summary,
                            date=new_date.isoformat(),
                            description=description,
                        )
                        sheets.update_cell("deadlines", dr_index, "calendar_event_id", new_event_id)
                        logger.info(
                            f"Calendar event updated for {dr['etapa']} ({dr['artista']} - {dr['titulo']}): {new_event_id}"
                        )
                    except Exception as cal_err:
                        logger.error(
                            f"Calendar update FAILED for {dr['etapa']} ({dr['artista']} - {dr['titulo']}): {cal_err}"
                        )
                changes.append(f"  - {dr['etapa']}: {old_date} → {new_date}")
                logger.info(
                    f"Cascaded {dr['etapa']} for {row['artista']} - {row['titulo']}: {old_date} → {new_date}"
                )

            changes_str = "\n".join(changes)
            subject = f"Balters — Prazos atualizados por atraso: {row['artista']} - {row['titulo']}"
            body = (
                f"Olá equipe,\n\n"
                f"Devido ao atraso na etapa '{row['etapa']}' ({delay_days} dia(s)), "
                f"os seguintes prazos foram atualizados automaticamente:\n\n"
                f"{changes_str}\n\n"
                f"Verifiquem a planilha para conferir.\n\n"
                f"Balters Records"
            )
            gmail.send_email(EMAIL_EQUIPE, subject, body)
            cascaded_set.add(release_key)
            logger.info(f"Cascade summary sent for {row['artista']} - {row['titulo']}")

        except Exception as e:
            logger.error(f"Error during cascade for row {row}: {e}")
            continue


def run_weekly(sheets, gmail) -> None:
    """Sends a weekly status summary email to EMAIL_EQUIPE every Monday."""
    today = date.today()
    week_end = today + timedelta(days=7)
    rows = sheets.get_rows("deadlines")

    overdue_rows: list[dict] = []
    upcoming_rows: list[dict] = []
    completed_rows: list[dict] = []

    for row in rows:
        try:
            deadline_date = _parse_date(row["deadline"])
            if row["status"] == "Pendente" and deadline_date < today:
                overdue_rows.append(row)
            elif row["status"] == "Pendente" and today <= deadline_date <= week_end:
                upcoming_rows.append(row)
            elif row["status"] == "Concluído":
                completed_rows.append(row)
        except Exception as e:
            logger.error(f"Error parsing row for weekly summary: {e}")
            continue

    if not overdue_rows and not upcoming_rows and not completed_rows:
        logger.info("Weekly summary: no active releases, skipping.")
        return

    def group_by_release(rows_list: list[dict]) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for r in rows_list:
            key = f"{r['artista']} - {r['titulo']}"
            grouped.setdefault(key, []).append(f"{r['etapa']} ({r['deadline']})")
        return grouped

    def format_section(header: str, rows_list: list[dict]) -> str:
        if not rows_list:
            return f"{header}\n  (nenhuma)"
        grouped = group_by_release(rows_list)
        lines = [header]
        for release, etapas in grouped.items():
            lines.append(f"\n{release}:")
            for etapa in etapas:
                lines.append(f"  - {etapa}")
        return "\n".join(lines)

    section1 = format_section("🔴 ETAPAS VENCIDAS", overdue_rows)
    section2 = format_section("🟡 PRÓXIMOS PRAZOS (7 dias)", upcoming_rows)
    section3 = format_section("✅ ETAPAS CONCLUÍDAS", completed_rows)

    body = f"{section1}\n\n{section2}\n\n{section3}"
    subject = f"Balters — Weekly Release Status {today.isoformat()}"
    gmail.send_email(EMAIL_EQUIPE, subject, body)
    logger.info("Weekly summary sent.")
