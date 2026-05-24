"""Manual test for the demo screening agent."""

import sys

from dotenv import load_dotenv

load_dotenv()

import anthropic
from integrations.sheets_client import SheetsClient, SHEET_DEMOS
from integrations.gmail_client import GmailClient
from prompts.prompts import DEMO_SCREENING_PROMPT
from agents.demo_screening import _parse_response, run as agent_run

MOCK_SUBMISSIONS = [
    {
        "_row_index": 1,
        "nome_artistico": "DJ Teste",
        "genero": "Indie Dance",
        "link_track": "https://soundcloud.com/djteste/track1",
        "link_perfil": "https://instagram.com/djteste",
        "mensagem": "Oi, segue minha track!",
        "email_artista": "teste@teste.com",
    },
    {
        "_row_index": 2,
        "nome_artistico": "MC Exemplo",
        "genero": "Funk",
        "link_track": "https://soundcloud.com/mcexemplo/track1",
        "link_perfil": "",
        "mensagem": "",
        "email_artista": "teste@teste.com",
    },
    {
        "_row_index": 3,
        "nome_artistico": "Artista Sem Link",
        "genero": "House",
        "link_track": "",
        "link_perfil": "",
        "mensagem": "",
        "email_artista": "teste@teste.com",
    },
]


def _screen_row(row: dict, claude) -> None:
    nome_artistico = str(row.get("nome_artistico", "")).strip()
    genero = str(row.get("genero", "")).strip()
    link_track = str(row.get("link_track", "")).strip()
    link_perfil = str(row.get("link_perfil", "")).strip()
    mensagem = str(row.get("mensagem", "")).strip()
    email_artista = str(row.get("email_artista", "")).strip()

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
    print(f"EMAIL_ARTISTA: {email_artista}")
    print(f"MENSAGEM_ARTISTA:\n{mensagem_artista}")


def run_mock() -> None:
    print("Mode: MOCK — hardcoded submissions, real Claude, no Sheets or email.\n")
    claude = anthropic.Anthropic()

    for row in MOCK_SUBMISSIONS:
        _screen_row(row, claude)


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
        and str(r.get("processado", "")).strip().upper() != "TRUE"
    ]

    print(f"{len(pending)} unprocessed submission(s) found.\n")

    if not pending:
        print("Nothing to process.")
        return

    for row in pending:
        _screen_row(row, claude)


def run_live() -> None:
    print("Mode: LIVE — delegates to agents.demo_screening.run().\n")

    try:
        sheets = SheetsClient()
        gmail = GmailClient()
        claude = anthropic.Anthropic()
    except Exception as e:
        print(f"Client init failed: {e}")
        sys.exit(1)

    agent_run(sheets=sheets, gmail=gmail, claude=claude)


if __name__ == "__main__":
    if "--mock" in sys.argv:
        run_mock()
    elif "--dry-run" in sys.argv:
        run_dry()
    elif "--live" in sys.argv:
        run_live()
    else:
        print("Usage: python test_demo_screening.py --dry-run | --mock | --live")
