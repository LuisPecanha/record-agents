# Balters Agents

AI automation system for **Balters Records**, an independent House/Indie Dance label. Four specialized agents handle recurring operational tasks — email triage, release scheduling, demo screening, and press kit generation — powered by the Claude API and integrated with Google Workspace.

## Agents

| Agent | Description |
|---|---|
| `email_triage` | Reads incoming Gmail messages, classifies them by type and urgency, and drafts prioritized responses |
| `release_calendar` | Manages release schedules by creating and updating Google Calendar events based on label deadlines |
| `demo_screening` | Evaluates demo submissions against Balters' sound profile and generates structured feedback |
| `press_kit` | Assembles and updates press kit content by pulling artist data from Google Sheets |

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| AI | Anthropic SDK — `claude-sonnet-4-5` |
| Google integrations | Gmail API, Google Calendar API, Google Sheets API (`google-auth`, `google-api-python-client`) |
| Orchestration | APScheduler |
| Deploy | Railway |

## Setup

## Deploy
