"""Unit tests for pure utility functions in integrations/utils.py."""

import pytest
from datetime import date

from integrations.utils import _parse_date, _extract_email


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value, expected", [
    # DD/MM/YYYY
    ("17/05/2025",   date(2025, 5, 17)),
    ("01/01/2024",   date(2024, 1, 1)),
    ("31/12/2023",   date(2023, 12, 31)),
    # YYYY-MM-DD
    ("2025-05-17",   date(2025, 5, 17)),
    ("2024-01-01",   date(2024, 1, 1)),
    ("2023-12-31",   date(2023, 12, 31)),
    # leading/trailing whitespace is stripped
    ("  17/05/2025 ", date(2025, 5, 17)),
    ("  2025-05-17 ", date(2025, 5, 17)),
])
def test_parse_date_valid(value, expected):
    assert _parse_date(value) == expected


@pytest.mark.parametrize("value", [
    "",           # empty
    "not-a-date",
    "32/01/2025", # day out of range
    "2025/05/17", # wrong separator for ISO
    "17-05-2025", # DD-MM-YYYY not supported
    "05/17/2025", # MM/DD/YYYY not supported
])
def test_parse_date_invalid_raises_value_error(value):
    with pytest.raises(ValueError, match="Unrecognized date format"):
        _parse_date(value)


def test_parse_date_none_raises_attribute_error():
    with pytest.raises(AttributeError):
        _parse_date(None)


def test_parse_date_returns_date_not_datetime():
    result = _parse_date("17/05/2025")
    assert type(result) is date


# ---------------------------------------------------------------------------
# _extract_email
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("from_field, expected", [
    # standard "Name <email>" format
    ("John Doe <john@example.com>",          "john@example.com"),
    ("Balters Records <info@balters.com>",   "info@balters.com"),
    ("José Artista <jose@balters.com>",      "jose@balters.com"),
    # just angle brackets, no display name
    ("<test@balters.com>",                   "test@balters.com"),
    # whitespace inside brackets is stripped
    ("Name < john@example.com >",            "john@example.com"),
    # bare email — no brackets, returns stripped input
    ("john@example.com",                     "john@example.com"),
    ("  john@example.com  ",                 "john@example.com"),
    # empty string
    ("",                                     ""),
])
def test_extract_email(from_field, expected):
    assert _extract_email(from_field) == expected


def test_extract_email_returns_first_match_when_multiple_brackets():
    # re.search finds the first occurrence
    result = _extract_email("Name <a@first.com> other <b@second.com>")
    assert result == "a@first.com"


def test_extract_email_returns_str():
    assert isinstance(_extract_email("test@example.com"), str)
    assert isinstance(_extract_email("Name <test@example.com>"), str)
