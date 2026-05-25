# Balters Agents — CLAUDE.md

## WORKING RULES FOR THIS CHAT

- Go step by step — don't write multiple things at once
- Every prompt has one responsibility (atomic)
- .env is never committed
- Answer in English
- Don't assume. Don't hide confusion. Surface tradeoffs.
- Minimum code that solves the problem. Nothing speculative.
- Touch only what you must. Clean up only your own mess.
- Define success criteria. Loop until verified.

## Project

AI automation system for Balters Records, an independent House/Indie Dance label. Six agents handle recurring operational tasks, orchestrated by APScheduler and powered by the Claude API.

## Stack

- Python 3.11+
- Anthropic SDK — `claude-sonnet-4-5`
- Gmail via IMAP/SMTP (App Password) — no OAuth
- Google Sheets via `gspread` + Service Account JSON
- Google Calendar via `googleapiclient` + Service Account JSON
- APScheduler (`BlockingScheduler` + `CronTrigger`)
- Deploy target: Railway

## Folder structure

```text
balters-agents/
├── agents/          # Business logic — one file per agent, each exposes run()
├── integrations/    # API clients only, no business logic
├── prompts/         # Prompt string constants
├── press_kits/      # Locally saved press kit .txt files (year/month subfolders)
├── scheduler/       # Entry point (main.py)
├── pytest.ini       # testpaths=tests, python_files=test_*.py, python_functions=test_*
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── agents/        # Pure-function unit tests for each agent
    │   ├── automations/   # Pure-function unit tests for automation helpers
    │   └── integrations/  # Pure-function unit tests for integration utilities
    ├── integration/       # Real-connection tests (no permanent writes)
    └── e2e/               # End-to-end scripts with real side effects
```

## Design decisions

- `agents/` owns Balters business logic. `integrations/` owns API mechanics. They must stay separate.
- `scheduler/main.py` inserts the project root into `sys.path` so `python scheduler/main.py` works from the repo root.
- The scheduler pings the Claude API once at boot as a connectivity check, then starts the interval jobs.
- Clients (sheets, gmail, calendar, claude) are instantiated once at boot and shared across all agents and scheduled jobs.
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
- `get_rows(sheet_name, anchor="artista")` — returns list of dicts with injected `_row_index` key (1-based, skips header); filters out rows where the `anchor` field is empty; callers pass `anchor="nome_artista"` for the lancamentos tab
- `append_row(sheet_name, row)` — accepts dict keyed by column header; USER_ENTERED input option
- `update_cell(sheet_name, row_index, col_name, value)` — resolves column by header name
- Tab constants: `SHEET_LANCAMENTOS`, `SHEET_DEADLINES`, `SHEET_EMAIL_LOG`, `SHEET_DEMOS`

### integrations/calendar_client.py

- `CalendarClient` — Google Calendar API v3, Service Account auth, scope `https://www.googleapis.com/auth/calendar`
- `create_event(summary, date, description)` — creates an all-day event; `date` is `YYYY-MM-DD`; returns the created event's `id`
- `delete_event(event_id)` — deletes an event by ID
- `list_events(time_min, time_max)` — returns list of event dicts from `items`; `singleEvents=True`, `orderBy="startTime"`; both params are ISO 8601 strings

### integrations/utils.py

- `_parse_date(value)` — accepts `DD/MM/YYYY` or `YYYY-MM-DD`; returns `date` object; raises `ValueError` on unrecognised format
- `_extract_email(from_field)` — extracts bare email from `"Name <email>"` format; returns stripped input if no angle brackets found
- `ETAPA_EMOJI` — dict mapping each deadline stage name to its emoji

### prompts/prompts.py

- `EMAIL_TRIAGE_PROMPT` — classifies emails into DEMO/IMPRENSA/PARCERIA/BOOKING/OUTRO and generates a draft reply. Output: `CLASSIFICACAO: X` / `RASCUNHO: ...`
- `DEMO_SCREENING_PROMPT` — generates the personalized artist message for APROVADO submissions. Output: `RESULTADO: X` / `MOTIVO: ...` / `MENSAGEM_ARTISTA: ...`
- `PRESS_KIT_PROMPT` — generates press copy from release data. Output: three delimited blocks `=== PRESS KIT BLURB ===`, `=== RELEASE NOTES ===`, `=== SOCIAL CAPTION ===`. Accepts `{release_data}` placeholder. Never invents facts not in input.

### agents/email_triage.py

- `run(gmail, sheets, claude, dry_run)` — full triage loop
- Module-level `APPROVER_EMAILS` list parsed from `APPROVER_EMAILS` env var (comma-separated)
- `_should_skip(from_field)` — returns True if sender matches any pattern in `_SKIP_PATTERNS` (`no-reply`, `noreply`, `accounts.google.com`, `googlecommunityteam`); case-insensitive substring match
- `_parse_response(text)` — parses `CLASSIFICACAO:` and `RASCUNHO:` from Claude's raw response; returns `(classification, draft)` tuple
- `_reply_subject(subject)` — adds `Re:` prefix if subject does not already start with `re:` (case-insensitive)
- `_build_notification_body(from_field, subject, classification, draft)` — assembles the approval-request email body sent to `APPROVER_EMAILS`
- Uses `claude-sonnet-4-5`, max_tokens=1024
- Creates draft reply, marks message as read
- **Phase 1.5**: after a successful draft creation, sends a notification email to all `APPROVER_EMAILS` with the full draft text and a prompt to reply with `APROVADO`; notification subject prefixed with `[APROVACAO PENDENTE]`
- Logs to `email_log` sheet via `append_row`: `data`, `remetente`, `assunto`, `classificacao`, `rascunho`, `notification_sent`, `notification_thread_id`, `aprovado=FALSE`, `enviado=FALSE`
- `dry_run=True` skips all writes and prints parsed output

### agents/release_calendar.py

- `run(sheets, gmail, calendar=None, dry_run=False)` — reads `lancamentos`, filters unprocessed rows
- `_compute_deadlines(release_date, artist, track)` — pure function; returns list of 8 deadline dicts from `_DEADLINES` offsets (days before release date: -42, -35, -28, -21, -14, -14, -7, -3)
- Each deadline dict: `etapa`, `deadline` (DD/MM/YYYY), `_date` (date object), `artista`, `titulo`
- For each deadline: creates a Google Calendar all-day event (if `calendar` is not None); writes deadline row to `deadlines` tab
- Calendar event summary format: `[{emoji} {etapa}] {track} — {artist}` using `ETAPA_EMOJI` dict
- Sends targeted emails: `EMAIL_DESIGN` (arte do single), `EMAIL_DISTRIBUTION` (entrega para distribuição), `EMAIL_EQUIPE` (full summary)
- Marks release as processed (`processado = True`)
- Sheet columns: `nome_artista`, `titulo_track`, `data_lancamento`, `processado`

### agents/demo_screening.py

- `run(sheets, gmail, claude)` — reads `demos` tab, filters unprocessed rows
- `_REJECTED_GENRES` — frozenset: `techno`, `trance`, `pop`, `hip hop`, `funk`, `sertanejo`; matched case-insensitively as substring of declared genre
- `_evaluate_submission(nome_artistico, genero, link_track)` — pure Python evaluation; returns `(resultado, motivo)`:
  - Missing `nome_artistico` → `INCOMPLETO`
  - Missing `link_track` → `INCOMPLETO`
  - Genre matches `_REJECTED_GENRES` → `REPROVADO`
  - Otherwise → `APROVADO`
- Claude is called **only for APROVADO** submissions (generates the personalized `MENSAGEM_ARTISTA`)
- REPROVADO uses `_REPROVADO_TEMPLATE` (hardcoded rejection message); INCOMPLETO sends empty body
- Email routing:
  - **APROVADO**: sends Claude-generated `MENSAGEM_ARTISTA` to `email_artista`; sends team notification to `EMAIL_SOCIAL` + `EMAIL_AR`
  - **REPROVADO**: sends `_REPROVADO_TEMPLATE` to `email_artista`; no team notification
  - **INCOMPLETO**: sends email with empty body to `email_artista` if address is present
- Sheet columns: `timestamp`, `nome_artistico`, `genero`, `link_track`, `link_perfil`, `mensagem`, `email_artista`, `resultado`, `motivo`, `processado`

### agents/press_kit.py

- `run(sheets, gmail, claude)` — reads `lancamentos` tab, filters rows where `processado_presskit != TRUE` and `nome_artista` is not empty
- `_build_release_data(row)` — assembles non-empty sheet fields into a `Label: value` string passed to Claude
- `_parse_blocks(text)` — splits Claude response on `===` delimiters into `(blurb, release_notes, social_caption)`; each part is stripped; extra spaces between `===` and header name are handled
- `_format_file_content(blurb, release_notes, social_caption)` — assembles the `.txt` file body with 60-char `=` separators and section headers
- `_build_filename(nome_artista, titulo_track, data_lancamento)` — sanitizes to safe `.txt` filename: spaces → underscores, slashes → hyphens, all lowercase
- Uses `claude-sonnet-4-5`, max_tokens=2000
- Saves generated copy to `press_kits/{year}/{month}/{filename}.txt`; sends with attachment to `EMAIL_DESIGN`
- Marks `processado_presskit = True`
- Sheet columns: `nome_artista`, `titulo_track`, `genero`, `data_lancamento`, `descricao`, `link_track`, `link_perfil`, `processado_presskit`

### agents/draft_approval.py

- `run(gmail, sheets)` — Phase 1.5 approval loop; no Claude call
- Module-level `APPROVER_EMAILS` list parsed from `APPROVER_EMAILS` env var
- `_is_pending(row)` — returns True if `notification_sent=TRUE`, `aprovado=FALSE`, `enviado=FALSE`; handles string and boolean values from gspread; case-insensitive
- `_is_approver_reply(reply, approver_emails)` — extracts sender email via `_extract_email`, checks case-insensitive membership in approver list
- `_reply_is_approved(reply)` — checks lowercased body for `"aprovado"` keyword; negation guard: returns False if body contains `"não aprovado"` or `"nao aprovado"` before the keyword check
- On approval: sends stored `rascunho` to `remetente`, updates `aprovado=TRUE` and `enviado=TRUE` in sheet
- Prints waiting log line if no qualifying reply yet

### agents/deadline_tracking.py

- `run_daily(sheets, gmail, calendar=None)` — alert and cascade logic; no Claude call
- `run_weekly(sheets, gmail)` — weekly status summary email; no Claude call
- Module-level `ETAPA_TO_EMAIL` dict mapping each deadline etapa to its responsible email address
- `get_responsible(etapa)` helper — returns email or None
- **Alert logic** (run_daily, first pass over deadlines rows):
  - Approaching (0–3 days, Pendente, alerta_enviado=FALSE): sends email to responsible person
  - Overdue (past deadline, Pendente, alerta_enviado=FALSE): sends email to responsible + `EMAIL_EQUIPE`
  - Both set `alerta_enviado=TRUE` in sheet after sending
- **Cascade logic** (run_daily, second pass):
  - Rows with `status=Atrasado`: shifts all downstream deadlines for the same release by delay_days
  - `alerta_enviado` reset to FALSE only if currently FALSE (skips if already TRUE — alert was sent this run)
  - If `calendar` is not None and row has `calendar_event_id`: deletes old event and creates a new one at the shifted date; updates `calendar_event_id` in sheet
  - Sends cascade summary to `EMAIL_EQUIPE`; `cascaded_set` prevents double-cascading a release in one run
- **Weekly summary** (run_weekly): groups overdue, upcoming (7 days), and completed rows by release; sends formatted email to `EMAIL_EQUIPE`; skips if no active rows

## scheduler/main.py

- Instantiates `SheetsClient`, `GmailClient`, `CalendarClient`, and `anthropic.Anthropic` once at boot — shared across all agents
- Runs email_triage, release_calendar, demo_screening, press_kit on boot; draft_approval and deadline_tracking do NOT run on boot
- Interval jobs (60 min): email_triage, demo_screening, press_kit; release_calendar passes `sheets`, `gmail`, `calendar` via `kwargs`
- Interval job (15 min): draft_approval — passes `gmail` and `sheets` via `kwargs`
- CronTrigger jobs: deadline_tracking daily at 09:00 (passes `calendar`) and weekly on Monday at 09:00

## Tests

Run unit tests: `pytest tests/unit/ -v`

179 unit tests, 0 failures. All tests are pure-logic with no I/O or API calls.

| File | Tests | Covers |
| --- | --- | --- |
| `tests/unit/agents/test_release_calendar.py` | 13 | `_compute_deadlines` |
| `tests/unit/agents/test_demo_screening.py` | 18 | `_evaluate_submission` |
| `tests/unit/agents/test_email_triage.py` | 39 | `_parse_response`, `_reply_subject`, `_build_notification_body`, `_should_skip` |
| `tests/unit/agents/test_press_kit.py` | 28 | `_build_release_data`, `_parse_blocks`, `_format_file_content`, `_build_filename` |
| `tests/unit/agents/test_draft_approval.py` | 43 | `_is_pending`, `_is_approver_reply`, `_reply_is_approved` |
| `tests/unit/automations/test_deadline_tracking.py` | 12 | `_parse_date` |
| `tests/unit/integrations/test_utils.py` | 26 | `_parse_date`, `_extract_email` |

## E2E and integration scripts

All manual test scripts moved into `tests/`. Run directly with `python tests/e2e/...` — these are not collected by pytest.

| Script | Purpose |
| --- | --- |
| `tests/e2e/test_email_triage.py` | `--mock`, `--gmail`, `--live`, default dry-run |
| `tests/e2e/test_release_calendar.py` | `--dry-run`, `--live` (appends test row + full run) |
| `tests/e2e/test_demo_screening.py` | `--mock`, `--dry-run`, `--live` (processes first pending row) |
| `tests/e2e/test_press_kit.py` | `--mock`, `--dry-run`, `--live` (processes first pending row, local file + attachment) |
| `tests/e2e/test_deadline_tracking.py` | `--mock`, `--dry-run`, `--live` |
| `tests/e2e/test_draft_approval.py` | `--mock`, `--dry-run`, `--live` |
| `tests/integration/test_sheets_connection.py` | Verifies connection to all four tabs |
| `tests/integration/test_smtp.py` | Sends a test email to `EMAIL_EQUIPE` via SMTP |
| `tests/integration/test_calendar_client.py` | `--auth` (list events), `--create` (test event), `--delete EVENT_ID`, `--purge` (delete all events 2020–2030), `--live` (full release_calendar run with real clients) |

## Environment variables

| Variable | Used by |
| --- | --- |
| `ANTHROPIC_API_KEY` | All agents via Claude |
| `BALTERS_EMAIL` | GmailClient (IMAP + SMTP sender) |
| `GMAIL_APP_PASSWORD` | GmailClient |
| `GOOGLE_SERVICE_ACCOUNT_PATH` | SheetsClient (default: `balters_sheets_service_account.json`) |
| `GOOGLE_SHEETS_ID_RELEASES` | SheetsClient |
| `GOOGLE_CALENDAR_ID` | CalendarClient |
| `APPROVER_EMAILS` | email_triage, draft_approval (comma-separated list) |
| `EMAIL_EQUIPE` | release_calendar, deadline_tracking, test_smtp |
| `EMAIL_DESIGN` | release_calendar, press_kit, deadline_tracking |
| `EMAIL_DISTRIBUTION` | release_calendar, deadline_tracking |
| `EMAIL_MASTERING` | deadline_tracking |
| `EMAIL_SOCIAL` | demo_screening |
| `EMAIL_AR` | demo_screening |

## Next steps

1. Fill in Setup and Deploy sections in `README.md`
2. Configure Railway deployment
