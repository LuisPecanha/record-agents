"""Manual test for the demo screening agent."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from integrations.sheets_client import SheetsClient, SHEET_DEMOS
from integrations.gmail_client import GmailClient
from prompts.prompts import DEMO_SCREENING_PROMPT
import anthropic

MOCK_SUBMISSIONS = [
    {
        "_row_index": 1,
        "nome_artistico": "DJ Teste",
        "genero": "Indie Dance",
        "link_track": "https://soundcloud.com/djteste/track1",
        "link_perfil": "https://instagram.com/djteste",
        "mensagem": "Oi, segue minha track!",
    },
    {
        "_row_index": 2,
        "nome_artistico": "MC Exemplo",
        "genero": "Funk",
        "link_track": "https://soundcloud.com/mcexemplo/track1",
        "link_perfil": "",
        "mensagem": "",
    },
    {
        "_row_index": 3,
        "nome_artistico": "Artista Sem Link",
        "genero": "House",
        "link_track": "",
        "link_perfil": "",
        "mensagem": "",
    },
]


def _parse_response(text: str) -> tuple[str, str, str]:
    resultado = ""
    motivo = ""
    mensagem_artista = ""
    for line in text.split("\n"):
        if line.startswith("RESULTADO:"):
            resultado = line.split(":", 1)[1].strip()
        elif line.startswith("MOTIVO:"):
            motivo = line.split(":", 1)[1].strip()
        elif line.startswith("MENSAGEM_ARTISTA:"):
            mensagem_artista = line.split(":", 1)[1].strip()
    return resultado, motivo, mensagem_artista


def _screen_submission(row: dict, claude) -> None:
    nome_artistico = str(row.get("nome_artistico", "")).strip()
    genero = str(row.get("genero", "")).strip()
    link_track = str(row.get("link_track", "")).strip()
    link_perfil = str(row.get("link_perfil", "")).strip()
    mensagem = str(row.get("mensagem", "")).strip()

    print(f"\n--- Submission: {nome_artistico} ---")

    if not nome_artistico or not link_track:
        resultado = "INCOMPLETO"
        motivo = "Campos obrigatórios ausentes: " + (
            "nome artístico" if not nome_artistico else "link da track"
        )
        print(f"RESULTADO: {resultado}")
        print(f"MOTIVO: {motivo}")
        print("MENSAGEM_ARTISTA: (skipped — pre-check)")
        return

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
    print(f"RESULTADO: {resultado}")
    print(f"MOTIVO: {motivo}")
    print(f"MENSAGEM_ARTISTA:\n{mensagem_artista}")


def run_mock() -> None:
    print("Mode: MOCK — hardcoded submissions, real Claude, no Sheets or email.\n")
    claude = anthropic.Anthropic()

    for row in MOCK_SUBMISSIONS:
        _screen_submission(row, claude)


def run_dry() -> None:
    print("Mode: DRY RUN — real Sheets rows, real Claude, no writes or emails.\n")

    try:
        sheets = SheetsClient()
        claude = anthropic.Anthropic()
    except Exception as e:
        print(f"Client init failed: {e}")
        sys.exit(1)

    rows = sheets.get_rows(SHEET_DEMOS)
    pending = [
        r for r in rows
        if str(r.get("nome_artistico", "")).strip()
        and not r.get("processado")
    ]

    print(f"{len(pending)} unprocessed submission(s) found.\n")

    if not pending:
        print("Nothing to process.")
        return

    for row in pending:
        _screen_submission(row, claude)


def run_live() -> None:
    print("Mode: LIVE — processes first unprocessed row, writes to Sheets, sends emails.\n")

    try:
        sheets = SheetsClient()
        gmail = GmailClient()
        claude = anthropic.Anthropic()
    except Exception as e:
        print(f"Client init failed: {e}")
        sys.exit(1)

    rows = sheets.get_rows(SHEET_DEMOS)
    pending = [
        r for r in rows
        if str(r.get("nome_artistico", "")).strip()
        and not r.get("processado")
    ]

    if not pending:
        print("No unprocessed submissions found.")
        return

    row = pending[0]
    row_number = row["_row_index"]
    nome_artistico = str(row.get("nome_artistico", "")).strip()
    genero = str(row.get("genero", "")).strip()
    link_track = str(row.get("link_track", "")).strip()
    link_perfil = str(row.get("link_perfil", "")).strip()
    mensagem = str(row.get("mensagem", "")).strip()

    print(f"Processing row {row_number}: {nome_artistico}\n")

    if not nome_artistico or not link_track:
        resultado = "INCOMPLETO"
        motivo = "Campos obrigatórios ausentes: " + (
            "nome artístico" if not nome_artistico else "link da track"
        )
        mensagem_artista = ""
        print(f"Pre-check INCOMPLETO — {motivo}")
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
        print(f"Claude result: {resultado} — {motivo}")

    sheets.update_cell(SHEET_DEMOS, row_number, 7, resultado)
    sheets.update_cell(SHEET_DEMOS, row_number, 8, motivo)
    print(f"Sheet updated — resultado={resultado}, motivo={motivo}")

    if resultado == "APROVADO":
        email_matias = os.getenv("EMAIL_MATIAS")
        email_ronaldo = os.getenv("EMAIL_RONALDO")
        body = mensagem_artista + f"\n\nTrack: {link_track}\nPerfil: {link_perfil}"
        subject = f"[Demo APROVADO] {nome_artistico} — {genero}"
        for recipient in [email_matias, email_ronaldo]:
            if not recipient:
                print("Skipping notification — recipient env var not set.")
                continue
            sent = gmail.send_email(to=recipient, subject=subject, body=body)
            print(f"Email {'sent' if sent else 'FAILED'} → {recipient}")
    else:
        print("AVISO: email ao artista não enviado — campo email não existe no formulário")

    sheets.update_cell(SHEET_DEMOS, row_number, 9, True)
    print(f"Row {row_number} marked as processado=True")


if __name__ == "__main__":
    if "--mock" in sys.argv:
        run_mock()
    elif "--dry-run" in sys.argv:
        run_dry()
    elif "--live" in sys.argv:
        run_live()
    else:
        print("Usage: python test_demo_screening.py --dry-run | --mock | --live")
