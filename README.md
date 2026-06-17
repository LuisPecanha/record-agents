# ai-label-ops

Operational automation for an independent House/Indie Dance label, built as a single APScheduler background worker that runs five Claude-powered agents and one rule-based automation on a cron schedule. The system handles the repetitive parts of label ops — inbox triage, demo screening, press kit generation, release deadline management — without removing humans from decisions that require judgement.

This is both a working tool and a portfolio piece illustrating how to build reliable, auditable AI automation around external APIs with clear separation of concerns.

---

## Agents and automations

```text
Incoming email (IMAP)
  └─ email_triage         Classify → draft reply → notify approvers for sign-off
       └─ draft_approval  Poll for "APROVADO" reply → send approved draft to sender

Google Sheets (lancamentos tab)
  ├─ release_calendar     Compute 8 per-release deadlines → Sheets + Google Calendar
  └─ press_kit            Generate press blurb / release notes / social caption → email attachment

Google Sheets (demos tab)
  └─ demo_screening       Filter by genre and completeness → Claude message for approved demos only

Google Sheets (deadlines tab)
  └─ deadline_tracking    Daily alerts, overdue cascades, weekly summary (no Claude)
```

### email_triage + draft_approval

The inbox loop is split into two agents by design. `email_triage` reads every unread message via IMAP, calls Claude to classify it (DEMO / IMPRENSA / PARCERIA / BOOKING / OUTRO) and generate a draft reply, saves the draft to Gmail Drafts, then sends a notification email to the approver list with the full draft text. `draft_approval` runs on a separate 15-minute schedule, searches the inbox for replies to those notification threads, and only sends the draft if it finds a reply from a known approver containing "APROVADO". Nothing reaches an external sender without explicit human sign-off.

### demo_screening

Applies hard objective rules in pure Python first (missing fields → INCOMPLETO, rejected genre → REPROVADO) and only calls Claude for submissions that pass. This keeps API costs proportional to actual work and makes the rejection logic testable without mocking the Claude API.

### press_kit

Calls Claude with the release data from Sheets and parses three delimited output blocks (press blurb, release notes, social caption) into a `.txt` file, then emails it as an attachment to the design lead. The local file is intentionally ephemeral on Railway; the email is the durable copy.

### deadline_tracking

A rule-based automation — no Claude calls. Runs daily at 09:00 to send alerts for approaching and overdue deadlines, shifts all downstream deadlines for a release when one is marked late (cascade logic), and updates Google Calendar events to match. Runs weekly on Mondays to send a full status summary. Deliberately kept in `automations/` rather than `agents/` to make clear it involves no AI.

---

## Design decisions

**Human-in-the-loop for all outbound replies.** The label doesn't want AI sending emails to artists or journalists autonomously. The approval loop is not a safety feature bolted on afterward — it was the original requirement. Every external reply requires a human "APROVADO" before it leaves the system.

**OAuth2 via Gmail API instead of SMTP.** Railway's Hobby plan blocks outbound SMTP on port 465/587. The IMAP reading path still uses an App Password because the Gmail API read scope is more complex to set up and the inbox reads are non-sensitive. The two auth methods coexist in the same client class.

**Dual-mode service account credentials.** On Railway, secrets are injected as env vars; a JSON file can't be committed or reliably placed on the filesystem. The Sheets and Calendar clients check for `GOOGLE_SERVICE_ACCOUNT_JSON` (a JSON string) first, then fall back to `GOOGLE_SERVICE_ACCOUNT_PATH` (a file path) for local dev. No committed secrets, no different code paths in tests vs. production.

**agents/ vs automations/ split.** `deadline_tracking` makes no Claude calls. Placing it in `agents/` alongside Claude-based agents would misrepresent how the system works. The directory name is a factual claim about what's in it.

**APScheduler BlockingScheduler, single process.** Each agent runs synchronously. This avoids the complexity of a task queue for a workload that doesn't need concurrency — there's at most one inbox check every 60 minutes. Startup runs are each wrapped in a separate try/except so a failing agent doesn't prevent the scheduler from starting.

---

## Stack

| Layer | Library / Service |
| --- | --- |
| AI | Anthropic SDK — `claude-sonnet-4-5` |
| Scheduling | APScheduler 3.x — `BlockingScheduler` + `CronTrigger` |
| Gmail (read) | `imaplib` — IMAP4_SSL, App Password |
| Gmail (send) | `google-api-python-client` — Gmail API v1, OAuth2 |
| Sheets | `gspread` — Service Account |
| Calendar | `google-api-python-client` — Calendar API v3, Service Account |
| Runtime | Python 3.11 |
| Deploy | Railway (background worker, no public port) |
| Tests | pytest — unit / integration / e2e layers |

---

## Local setup

### Prerequisites

- Python 3.11
- A Google Cloud project with the Gmail API, Sheets API, and Calendar API enabled
- A Google Service Account with access to the target Sheets and Calendar
- A Gmail OAuth2 client (Desktop app type) for the sending account

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Generate a Gmail OAuth2 refresh token (one-time)

```bash
python scripts/get_gmail_token.py client_secret_<your-id>.json
# Opens a browser. After authorization, prints the refresh_token to stdout.
```

### Environment variables

Create a `.env` file at the repo root (never committed):

```dotenv
# Anthropic
ANTHROPIC_API_KEY=

# Gmail — IMAP (reading)
BALTERS_EMAIL=
GMAIL_APP_PASSWORD=

# Gmail — API OAuth2 (sending)
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_REFRESH_TOKEN=

# Google Sheets
GOOGLE_SERVICE_ACCOUNT_PATH=balters_sheets_service_account.json
GOOGLE_SHEETS_ID_RELEASES=

# Google Calendar
GOOGLE_CALENDAR_ID=

# Routing
APPROVER_EMAILS=             # comma-separated, receives draft approval requests
EMAIL_EQUIPE=                # receives release summaries and deadline alerts
EMAIL_DESIGN=                # receives press kits and design deadline alerts
EMAIL_DISTRIBUTION=          # receives distribution deadline alerts
EMAIL_MASTERING=             # receives mastering deadline alerts
EMAIL_SOCIAL=                # receives demo approval notifications
EMAIL_AR=                    # receives demo approval notifications (A&R)
```

On Railway, replace `GOOGLE_SERVICE_ACCOUNT_PATH` with `GOOGLE_SERVICE_ACCOUNT_JSON` (the full JSON content of the service account key as a single-line string).

### Run

```bash
python scheduler/main.py
```

Runs all agents once on boot, then starts the scheduled jobs.

---

## Testing

```bash
# Unit tests — pure logic, no I/O, no API calls (189 tests)
pytest tests/unit/ -v

# Integration tests — real credentials required, read-only, no writes or sends
pytest tests/integration/ -v -m integration

# E2E scripts — real side effects, run manually
python tests/e2e/test_email_triage.py --dry-run
python tests/e2e/test_release_calendar.py --dry-run
python tests/e2e/test_demo_screening.py --dry-run
python tests/e2e/test_press_kit.py --dry-run
python tests/e2e/test_deadline_tracking.py --dry-run
python tests/e2e/test_draft_approval.py --dry-run
```

Unit tests cover all pure functions: `_parse_response`, `_evaluate_submission`, `_compute_deadlines`, `_parse_blocks`, `_is_pending`, `_reply_is_approved`, `_parse_date`, `_extract_email`, and others. Integration tests verify real connections to Sheets, Gmail (IMAP), and Calendar without mutating any data.

---

## Deployment

Deployed on Railway as a background worker (`worker: python scheduler/main.py`). No public HTTP port. The `press_kits/` directory is written locally but treated as ephemeral — the press kit is always emailed as an attachment before the process could restart, so the local file is never the only copy.

Railway env vars replace all local `.env` entries. `GOOGLE_SERVICE_ACCOUNT_JSON` is used in place of a mounted file.
