# Balters Agents — CLAUDE.md

## Project

AI automation system for Balters Records, an independent House/Indie Dance label. Six agents handle recurring operational tasks, orchestrated by APScheduler and powered by the Claude API.

## Stack

- Python 3.11+
- Anthropic SDK — `claude-sonnet-4-5`
- Gmail via IMAP/SMTP (App Password) — no OAuth
- Google Sheets via `gspread` + Service Account JSON
- APScheduler (`BlockingScheduler` + `CronTrigger`)
- Deploy target: Railway

## Folder structure

```
balters-agents/
├── agents/          # Business logic — one file per agent, each exposes run()
├── integrations/    # API clients only, no business logic
├── prompts/         # Prompt string constants
├── press_kits/      # Locally saved press kit .txt files (year/month subfolders)
├── scheduler/       # Entry point (main.py)
└── tests/           # Pytest tests
```

## Design decisions

- `agents/` owns Balters business logic. `integrations/` owns API mechanics. They must stay separate.
- `scheduler/main.py` inserts the project root into `sys.path` so `python scheduler/main.py` works from the repo root.
- The scheduler pings the Claude API once at boot as a connectivity check, then starts the interval jobs.
- Clients (sheets, gmail, claude) are instantiated once at boot and shared across all agents and scheduled jobs.
- Gmail auth uses App Password + IMAP/SMTP (imaplib/smtplib). No OAuth, no Google Cloud Console flow.
- Sheets auth uses a Service Account JSON file. Path read from `GOOGLE_SERVICE_ACCOUNT_PATH` env var (default: `balters_sheets_service_account.json`).
- `update_cell(sheet_name, row_index, col_name, value)` resolves columns by header name — never by numeric index.
- `append_row(sheet_name, row)` accepts a dict keyed by column header name — values are mapped positionally via `row.get(h, "")`.
- `processado` is a Google Sheets checkbox. gspread may return it as boolean `False`/`True` or strings `"FALSE"`/`"TRUE"`. All agents normalize with `str(...).strip().upper() != "TRUE"` to filter unprocessed rows, and write `True` to mark as done.
- Empty sheet rows (default unchecked checkboxes) are excluded by requiring the primary name field to be non-empty.
- `send_email()` returns the Message-ID string on success, `""` on failure. Supports multiple recipients via comma-separated `to` string.
- `create_draft()` is used for triage replies requiring human review before sending.
- Press kit copy is saved as a local `.txt` file under `press_kits/{year}/{month}/` and attached to the notification email — no Google Drive, no Sheets columns for copy.

## Implemented

### integrations/gmail_client.py
- `GmailClient` — IMAP4_SSL + SMTP_SSL, App Password auth
- `get_unread_messages()` — BODY.PEEK (no auto-read), returns list of dicts with `id`, `thread_id`, `from`, `subject`, `body`, `date`
- `create_draft()` — appends to `"[Gmail]/Drafts"` via IMAP APPEND
- `mark_as_read()` — sets `\Seen` flag via UID STORE
- `list_folders()` — prints all IMAP folders (used for debugging)
- `send_email(to, subject, body)` — sends plain-text email via SMTP_SSL port 465; `to` may be comma-separated for multiple recipients; returns Message-ID string on success, `""` on failure
- `send_email_with_attachment(to, subject, body, attachment_content, attachment_filename)` — same as above with a plain-text MIME attachment
- `get_replies_to_thread(thread_id)` — searches INBOX for messages matching `In-Reply-To` or `References` headers; returns list of `{"from": ..., "body": ...}` dicts; read-only (BODY.PEEK)

### integrations/sheets_client.py
- `SheetsClient` — gspread + Service Account, connects to `GOOGLE_SHEETS_ID_RELEASES`
- `get_rows(sheet_name)` — returns list of dicts with injected `_row_index` key (1-based, skips header)
- `append_row(sheet_name, row)` — accepts dict keyed by column header; USER_ENTERED input option
- `update_cell(sheet_name, row_index, col_name, value)` — resolves column by header name
- Tab constants: `SHEET_LANCAMENTOS`, `SHEET_DEADLINES`, `SHEET_EMAIL_LOG`, `SHEET_DEMOS`

### prompts/prompts.py
- `EMAIL_TRIAGE_PROMPT` — classifies emails into DEMO/IMPRENSA/PARCERIA/BOOKING/OUTRO and generates a draft reply. Output: `CLASSIFICACAO: X` / `RASCUNHO: ...`
- `DEMO_SCREENING_PROMPT` — screens demo submissions by genre and link presence. Output: `RESULTADO: X` / `MOTIVO: ...` / `MENSAGEM_ARTISTA: ...`
- `PRESS_KIT_PROMPT` — generates press copy from release data. Output: three delimited blocks `=== PRESS KIT BLURB ===`, `=== RELEASE NOTES ===`, `=== SOCIAL CAPTION ===`. Accepts `{release_data}` placeholder. Never invents facts not in input.

### agents/email_triage.py
- `run(gmail, sheets, claude, dry_run)` — full triage loop
- Module-level `APPROVER_EMAILS` list parsed from `APPROVER_EMAILS` env var (comma-separated)
- Skips automated senders: `no-reply`, `noreply`, `accounts.google.com`, `googlecommunityteam`
- Uses `claude-opus-4-5`, max_tokens=1024
- Parses Claude response, extracts email address from `Name <email>` format
- Creates draft reply, marks message as read
- **Phase 1.5**: after a successful draft creation, sends a notification email to all `APPROVER_EMAILS` with the full draft text and a prompt to reply with `APROVADO`; notification subject prefixed with `[APROVACAO PENDENTE]`
- Logs to `email_log` sheet via `append_row` with column-keyed dict: `data`, `remetente`, `assunto`, `classificacao`, `rascunho`, `notification_sent`, `notification_thread_id`, `aprovado=FALSE`, `enviado=FALSE`
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

### agents/press_kit.py
- `run(sheets, gmail, claude)` — reads `lancamentos` tab, filters rows where `processado_presskit != TRUE` and `nome_artista` is not empty
- Builds `release_data` string from available fields, skipping empty ones
- Uses `claude-sonnet-4-5`, max_tokens=2000
- Parses three output blocks by splitting on `===` delimiters
- Saves generated copy as a `.txt` file to `press_kits/{year}/{month}/{filename}.txt` under the project root (creates dirs with `exist_ok=True`)
- Sends email to `EMAIL_GUILHERME` with the `.txt` file attached via `send_email_with_attachment()`
- Marks `processado_presskit = True`
- Sheet columns used: `nome_artista`, `titulo_track`, `genero`, `data_lancamento`, `descricao`, `link_track`, `link_perfil`, `processado_presskit`

### agents/draft_approval.py
- `run(gmail, sheets)` — Phase 1.5 approval loop; no Claude call
- Module-level `APPROVER_EMAILS` list parsed from `APPROVER_EMAILS` env var
- Reads `email_log` tab, filters rows where `notification_sent=TRUE`, `aprovado=FALSE`, `enviado=FALSE`
- For each pending row, calls `gmail.get_replies_to_thread(notification_thread_id)` to find replies
- Filters replies by sender (must be in `APPROVER_EMAILS`, case-insensitive) and body (must contain `"APROVADO"`)
- On approval: sends the stored `rascunho` to `remetente`, updates `aprovado=TRUE` and `enviado=TRUE` in sheet
- Prints waiting log line if no qualifying reply yet

### agents/deadline_tracking.py
- `run_daily(sheets, gmail)` — alert and cascade logic; no Claude call
- `run_weekly(sheets, gmail)` — weekly status summary email; no Claude call
- Module-level `ETAPA_TO_EMAIL` dict mapping each deadline etapa to its responsible email address
- `get_responsible(etapa)` helper — returns email or None
- **Alert logic** (run_daily, first pass over deadlines rows):
  - Approaching (0–3 days, Pendente, alerta_enviado=FALSE): sends email to responsible person
  - Overdue (past deadline, Pendente, alerta_enviado=FALSE): sends email to responsible + `EMAIL_EQUIPE`
  - Both set `alerta_enviado=TRUE` in sheet after sending
- **Cascade logic** (run_daily, second pass):
  - Rows with `status=Atrasado`: shifts all downstream deadlines for the same release by delay_days
  - Resets `alerta_enviado=FALSE` on shifted rows; sends cascade summary to `EMAIL_EQUIPE`
  - `cascaded_set` prevents double-cascading a release in one run
- **Weekly summary** (run_weekly): groups overdue, upcoming (7 days), and completed rows by release; sends formatted email to `EMAIL_EQUIPE`; skips if no active rows

## scheduler/main.py
- Instantiates `SheetsClient`, `GmailClient`, and `anthropic.Anthropic` once at boot — shared across all agents
- Runs email_triage, release_calendar, demo_screening, press_kit on boot; draft_approval and deadline_tracking do NOT run on boot
- Interval jobs (60 min): email_triage, release_calendar, demo_screening, press_kit
- Interval job (15 min): draft_approval — passes `gmail` and `sheets` via `kwargs`
- CronTrigger jobs: deadline_tracking daily at 09:00 and weekly on Monday at 09:00

## Manual test scripts

| Script | Purpose |
|---|---|
| `test_email_triage.py` | `--mock`, `--gmail`, `--live`, default dry-run |
| `test_release_calendar.py` | `--dry-run`, `--live` (appends test row + full run) |
| `test_demo_screening.py` | `--mock`, `--dry-run`, `--live` (processes first pending row) |
| `test_press_kit.py` | `--mock`, `--dry-run`, `--live` (processes first pending row, local file + attachment) |
| `test_deadline_tracking.py` | `--mock`, `--dry-run`, `--live` |
| `test_sheets_connection.py` | Verifies connection to all tabs |
| `test_smtp.py` | Sends a test email to `EMAIL_EQUIPE` via SMTP |
| `tests/test_draft_approval.py` | `--mock`, `--dry-run`, `--live` |

## Environment variables

| Variable | Used by |
|---|---|
| `ANTHROPIC_API_KEY` | All agents via Claude |
| `BALTERS_EMAIL` | GmailClient (IMAP + SMTP sender) |
| `GMAIL_APP_PASSWORD` | GmailClient |
| `GOOGLE_SERVICE_ACCOUNT_PATH` | SheetsClient (default: `balters_sheets_service_account.json`) |
| `GOOGLE_SHEETS_ID_RELEASES` | SheetsClient |
| `APPROVER_EMAILS` | email_triage, draft_approval (comma-separated list) |
| `EMAIL_EQUIPE` | release_calendar, deadline_tracking, test_smtp |
| `EMAIL_GUILHERME` | release_calendar, press_kit, deadline_tracking |
| `EMAIL_LUIS` | release_calendar, deadline_tracking |
| `EMAIL_BLUMEL` | deadline_tracking |
| `EMAIL_MATIAS` | demo_screening |
| `EMAIL_RONALDO` | demo_screening |

## Next steps

1. Fill in Setup and Deploy sections in `README.md`
2. Write real tests in `tests/test_agents.py`
3. Configure Railway deployment
