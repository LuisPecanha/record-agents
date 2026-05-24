"""Shared utilities for integrations."""

import re
from datetime import date, datetime


ETAPA_EMOJI = {
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
    raise ValueError(f"Unrecognized date format: '{value}'. Expected DD/MM/YYYY or YYYY-MM-DD.")


def _extract_email(from_field: str) -> str:
    match = re.search(r"<(.+?)>", from_field)
    if match:
        return match.group(1).strip()
    return from_field.strip()
