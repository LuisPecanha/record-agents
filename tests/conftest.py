"""Shared fixtures for balters-agents test suite."""

import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(scope="session")
def sheets_client():
    from integrations.sheets_client import SheetsClient
    return SheetsClient()


@pytest.fixture(scope="session")
def gmail_client():
    from integrations.gmail_client import GmailClient
    return GmailClient()


@pytest.fixture(scope="session")
def calendar_client():
    from integrations.calendar_client import CalendarClient
    return CalendarClient()
