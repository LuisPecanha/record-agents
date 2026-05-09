# Balters Agents — CLAUDE.md

## Project

AI automation system for Balters Records, an independent House/Indie Dance label. Four agents handle recurring operational tasks, orchestrated by APScheduler and powered by the Claude API.

## Stack

- Python 3.11+
- Anthropic SDK — `claude-sonnet-4-5`
- Gmail via IMAP/SMTP (App Password) — no OAuth
- Google Sheets via `gspread` + Service Account JSON
- APScheduler (`BlockingScheduler`)
- Deploy target: Railway

## Folder structure

```
balters-agents/
├── agents/          # Business logic — one file per agent, each exposes run()
├── integrations/    # API clients only, no business logic
├── prompts/         # Prompt string constants
├── scheduler/       # Entry point (main.py)
└── tests/           # Pytest tests
```

## Design decisions

- `agents/` owns Balters business logic. `integrations/` owns API mechanics. They must stay separate.
- `scheduler/main.py` inserts the project root into `sys.path` so `python scheduler/main.py` works from the repo root.
- The scheduler pings the Claude API once at boot as a connectivity check, then starts the interval jobs.
- All agents run every 60 minutes via `add_job(..., "interval", minutes=60)`. Clients (sheets, gmail, claude) are instantiated once at boot and shared across all agents and scheduled jobs.
- Gmail auth uses App Password + IMAP/SMTP (imaplib/smtplib). No OAuth, no Google Cloud Console flow.
- Sheets auth uses a Service Account JSON file. Path read from `GOOGLE_SERVICE_ACCOUNT_PATH` env var (default: `balters_sheets_service_account.json`).
- `update_cell(sheet_name, row_index, col_name, value)` resolves columns by header name — never by numeric index.
- `processado` is a Google Sheets checkbox. gspread may return it as boolean `False`/`True` or strings `"FALSE"`/`"TRUE"`. All agents normalize with `str(...).strip().upper() != "TRUE"` to filter unprocessed rows, and write `True` to mark as done.
- Empty sheet rows (default unchecked checkboxes) are excluded by requiring the primary name field to be non-empty.
- `send_email()` is used for automated outbound notifications. `create_draft()` is used for triage replies requiring human review before sending.

## Implemented

### integrations/gmail_client.py
- `GmailClient` — IMAP4_SSL + SMTP_SSL, App Password auth
- `get_unread_messages()` — BODY.PEEK (no auto-read), returns list of dicts with `id`, `thread_id`, `from`, `subject`, `body`, `date`
- `create_draft()` — appends to `"[Gmail]/Drafts"` via IMAP APPEND
- `mark_as_read()` — sets `\Seen` flag via UID STORE
- `list_folders()` — prints all IMAP folders (used for debugging)
- `send_email()` — sends plain-text email via SMTP_SSL port 465

### integrations/sheets_client.py
- `SheetsClient` — gspread + Service Account, connects to `GOOGLE_SHEETS_ID_RELEASES`
- `get_rows(sheet_name)` — returns list of dicts with injected `_row_index` key (1-based, skips header)
- `append_row(sheet_name, row)` — USER_ENTERED input option
- `update_cell(sheet_name, row_index, col_name, value)` — resolves column by header name
- Tab constants: `SHEET_LANCAMENTOS`, `SHEET_DEADLINES`, `SHEET_EMAIL_LOG`, `SHEET_DEMOS`

### prompts/prompts.py
- `EMAIL_TRIAGE_PROMPT` — classifies emails into DEMO/IMPRENSA/PARCERIA/BOOKING/OUTRO and generates a draft reply. Output: `CLASSIFICACAO: X` / `RASCUNHO: ...`
- `DEMO_SCREENING_PROMPT` — screens demo submissions by genre and link presence. Output: `RESULTADO: X` / `MOTIVO: ...` / `MENSAGEM_ARTISTA: ...`

### agents/email_triage.py
- `run(gmail, sheets, claude, dry_run)` — full triage loop
- Skips automated senders: `no-reply`, `noreply`, `accounts.google.com`, `googlecommunityteam`
- Uses `claude-opus-4-5`, max_tokens=1024
- Parses Claude response, extracts email address from `Name <email>` format
- Creates draft reply, marks message as read, logs mock Sheets row
- `dry_run=True` skips all writes and prints parsed output

### agents/release_calendar.py
- `run(sheets, gmail, dry_run)` — reads `lancamentos`, filters unprocessed rows
- Calculates 8 deadlines from `data_lancamento` (accepts `DD/MM/YYYY` or `YYYY-MM-DD`)
- Writes each deadline to `deadlines` tab
- Sends targeted emails: `EMAIL_GUILHERME` (arte do single), `EMAIL_LUIS` (entrega para distribuição), `EMAIL_EQUIPE` (full summary)
- Marks release as processed (`processado = True`)
- Sheet columns: `nome_artista`, `titulo_track`, `data_lancamento`, `processado`

### agents/demo_screening.py
- `run(sheets, gmail, claude)` — reads `demos` tab, filters unprocessed rows
- Pre-check: flags as INCOMPLETO if `nome_artistico` or `link_track` is missing (skips Claude call)
- Uses `claude-sonnet-4-5`, max_tokens=1024
- Parses `RESULTADO`, `MOTIVO`, `MENSAGEM_ARTISTA` from Claude response (multi-line aware)
- Writes `resultado` and `motivo` back to sheet, marks `processado = True`
- Email routing:
  - **APROVADO**: sends `MENSAGEM_ARTISTA` to `email_artista`; sends team notification to `EMAIL_MATIAS` + `EMAIL_RONALDO`
  - **REPROVADO**: sends `MENSAGEM_ARTISTA` to `email_artista`; no team notification
  - **INCOMPLETO**: sends `MENSAGEM_ARTISTA` to `email_artista` if present; warns if empty
- Sheet columns: `timestamp`, `nome_artistico`, `genero`, `link_track`, `link_perfil`, `mensagem`, `email_artista`, `resultado`, `motivo`, `processado`

## Manual test scripts

| Script | Purpose |
|---|---|
| `test_email_triage.py` | `--mock`, `--gmail`, `--live`, default dry-run |
| `test_release_calendar.py` | `--dry-run`, `--live` (appends test row + full run) |
| `test_demo_screening.py` | `--mock`, `--dry-run`, `--live` (processes first pending row) |
| `test_sheets_connection.py` | Verifies connection to all tabs |
| `test_smtp.py` | Sends a test email to `EMAIL_EQUIPE` via SMTP |

## Environment variables

| Variable | Used by |
|---|---|
| `ANTHROPIC_API_KEY` | All agents via Claude |
| `BALTERS_EMAIL` | GmailClient (IMAP + SMTP sender) |
| `GMAIL_APP_PASSWORD` | GmailClient |
| `GOOGLE_SERVICE_ACCOUNT_PATH` | SheetsClient (default: `balters_sheets_service_account.json`) |
| `GOOGLE_SHEETS_ID_RELEASES` | SheetsClient |
| `EMAIL_EQUIPE` | release_calendar, test_smtp |
| `EMAIL_GUILHERME` | release_calendar |
| `EMAIL_LUIS` | release_calendar |
| `EMAIL_MATIAS` | demo_screening |
| `EMAIL_RONALDO` | demo_screening |

## Next steps

1. Implement `agents/press_kit.py` — reads release info from Sheets, generates press release + bio + captions with Claude
2. Write `PRESS_KIT_PROMPT` in `prompts/prompts.py`
3. Fill in Setup and Deploy sections in `README.md`
4. Write real tests in `tests/test_agents.py`
5. Configure Railway deployment
