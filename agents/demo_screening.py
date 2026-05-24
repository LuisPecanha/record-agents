"""Demo screening agent. Reads demo submissions from Google Sheets, uses Claude to screen by objective criteria (genre match, links present, form completeness) and routes to 3 possible outcomes: approve, reject, or request more info."""

import os

from integrations.sheets_client import SHEET_DEMOS
from prompts.prompts import DEMO_SCREENING_PROMPT


_ARTIST_SUBJECTS = {
    "APROVADO": "Recebemos sua demo — Balters Records",
    "REPROVADO": "Sobre sua demo — Balters Records",
    "INCOMPLETO": "Sua submissão está incompleta — Balters Records",
}


def _send_artist_email(gmail, email_artista: str, resultado: str, mensagem_artista: str) -> None:
    if not email_artista:
        print("[demo_screening] AVISO: email_artista vazio — email ao artista não enviado.")
        return
    subject = _ARTIST_SUBJECTS.get(resultado, "")
    sent = gmail.send_email(to=email_artista, subject=subject, body=mensagem_artista)
    print(f"[demo_screening] Artist email {'sent' if sent else 'FAILED'} → {email_artista}")


def _parse_response(text: str) -> tuple[str, str, str]:
    resultado = ""
    motivo = ""
    mensagem_artista = ""
    current_key = None

    for line in text.split("\n"):
        if line.startswith("RESULTADO:"):
            current_key = "resultado"
            resultado = line.split(":", 1)[1].strip()
        elif line.startswith("MOTIVO:"):
            current_key = "motivo"
            motivo = line.split(":", 1)[1].strip()
        elif line.startswith("MENSAGEM_ARTISTA:"):
            current_key = "mensagem_artista"
            mensagem_artista = line.split(":", 1)[1].strip()
        elif current_key == "mensagem_artista":
            mensagem_artista += "\n" + line

    mensagem_artista = mensagem_artista.strip()
    return resultado, motivo, mensagem_artista


def run(sheets, gmail=None, claude=None) -> None:
    print("\n" + "=" * 60)
    print("[demo_screening] Run started")
    print("=" * 60)

    email_social = os.getenv("EMAIL_SOCIAL")
    email_ar = os.getenv("EMAIL_AR")

    rows = sheets.get_rows(SHEET_DEMOS, anchor="nome_artistico")
    pending = [
        r for r in rows
        if str(r.get("nome_artistico", "")).strip()
        and str(r.get("processado", "")).strip().upper() != "TRUE"
    ]
    print(f"[demo_screening] {len(pending)} unprocessed submission(s) found.\n")

    for row in pending:
        row_number = row["_row_index"]
        nome_artistico = str(row.get("nome_artistico", "")).strip()
        genero = str(row.get("genero", "")).strip()
        link_track = str(row.get("link_track", "")).strip()
        link_perfil = str(row.get("link_perfil", "")).strip()
        mensagem = str(row.get("mensagem", "")).strip()
        email_artista = str(row.get("email_artista", "")).strip()

        print(f"[demo_screening] Processing row {row_number}: {nome_artistico}")

        try:
            if not nome_artistico or not link_track:
                resultado = "INCOMPLETO"
                motivo = "Campos obrigatórios ausentes: " + (
                    "nome artístico" if not nome_artistico else "link da track"
                )
                mensagem_artista = ""
                print(f"[demo_screening] Pre-check INCOMPLETO — {motivo}")
            else:
                prompt = DEMO_SCREENING_PROMPT.format(
                    nome_artistico=nome_artistico,
                    genero=genero,
                    link_track=link_track,
                    link_perfil=link_perfil,
                    mensagem=mensagem,
                )

                response = claude.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )

                resultado, motivo, mensagem_artista = _parse_response(response.content[0].text)
                print(f"[demo_screening] Claude result: {resultado} — {motivo}")

            sheets.update_cell(SHEET_DEMOS, row_number, "resultado", resultado)
            sheets.update_cell(SHEET_DEMOS, row_number, "motivo", motivo)
            print(f"[demo_screening] Sheet updated — resultado={resultado}, motivo={motivo}")

            _send_artist_email(gmail, email_artista, resultado, mensagem_artista)

            if resultado == "APROVADO":
                team_body = (
                    "Nova demo aprovada na triagem automática.\n\n"
                    f"Artista: {nome_artistico}\n"
                    f"Gênero: {genero}\n"
                    f"Track: {link_track}\n"
                    f"Perfil: {link_perfil}\n"
                    f"Email: {email_artista}\n\n"
                    "A track aguarda escuta humana."
                )
                team_subject = f"[Demo APROVADO] {nome_artistico} — {genero}"
                for recipient in [email_social, email_ar]:
                    if not recipient:
                        print("[demo_screening] Skipping team notification — recipient env var not set.")
                        continue
                    sent = gmail.send_email(to=recipient, subject=team_subject, body=team_body)
                    print(f"[demo_screening] Team email {'sent' if sent else 'FAILED'} → {recipient}")

            sheets.update_cell(SHEET_DEMOS, row_number, "processado", True)
            print(f"[demo_screening] Row {row_number} marked as processado=True\n")

        except Exception as e:
            print(f"[demo_screening] ERROR on row {row_number} ({nome_artistico}): {e}\n")

    print("[demo_screening] Run complete.\n")
