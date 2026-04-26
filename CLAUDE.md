# Balters Agents — CLAUDE.md

## Project

AI automation system for Balters Records, an independent House/Indie Dance label. Four agents handle recurring operational tasks, orchestrated by APScheduler and powered by the Claude API.

## Stack

- Python 3.11+
- Anthropic SDK — `claude-sonnet-4-5`
- Gmail API, Google Calendar API, Google Sheets API
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
- All 4 agents run every 60 minutes via `add_job(..., "interval", minutes=60)`.

## Session summary (2026-04-25)

Bootstrapped the full project skeleton from scratch:

- `README.md` — project description, agents table, stack table, empty Setup/Deploy sections
- `.gitignore` — Python, venv, `.env`, Google credentials, IDE, OS, Railway
- `.env.example` — all required env vars grouped by service
- `requirements.txt` — pinned: anthropic, google-auth, google-auth-oauthlib, google-api-python-client, apscheduler, python-dotenv
- `agents/` — stub files for all 4 agents (`email_triage`, `release_calendar`, `demo_screening`, `press_kit`), each with a docstring and empty `run()`
- `integrations/` — `GmailClient`, `CalendarClient`, `SheetsClient` stubs with method signatures
- `prompts/prompts.py` — empty prompt constants for 3 agents
- `tests/test_agents.py` — imports + 4 empty test functions
- `scheduler/main.py` — `.env` load, API key check, Claude ping, APScheduler setup, clean Ctrl+C exit
- Fixed `ModuleNotFoundError` by inserting project root into `sys.path` in `scheduler/main.py`

All files verified working: `python scheduler/main.py` runs, Claude responds, scheduler starts.

## Next steps

1. Implement `integrations/gmail_client.py` — OAuth flow, `get_unread_messages`, `create_draft`, `send_message`
2. Implement `integrations/calendar_client.py` — service account auth, `create_event`, `list_events`
3. Implement `integrations/sheets_client.py` — service account auth, `get_rows`, `append_row`, `update_row`
4. Write prompts in `prompts/prompts.py` for email triage, demo screening, press kit
5. Implement agent logic starting with `email_triage.py` (simplest, most isolated)
6. Fill in Setup and Deploy sections in `README.md`
7. Write real tests in `tests/test_agents.py`
8. Configure Railway deployment
