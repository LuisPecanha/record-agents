"""Integration tests: verifies CalendarClient can connect and list events (read-only)."""

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.integration


def test_calendar_client_initializes(calendar_client):
    assert calendar_client is not None


def test_calendar_list_events_returns_list(calendar_client):
    now = datetime.now(timezone.utc)
    time_min = now.strftime("%Y-%m-%dT00:00:00Z")
    time_max = (now + timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
    events = calendar_client.list_events(time_min=time_min, time_max=time_max)
    assert isinstance(events, list)


def test_calendar_event_items_have_expected_keys(calendar_client):
    now = datetime.now(timezone.utc)
    time_min = now.strftime("%Y-%m-%dT00:00:00Z")
    time_max = (now + timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
    events = calendar_client.list_events(time_min=time_min, time_max=time_max)
    for event in events:
        assert "id" in event
        assert "summary" in event or "status" in event
