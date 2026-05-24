"""Unit tests for _parse_date() in integrations/utils.py."""

import pytest
from datetime import date

from integrations.utils import _parse_date


@pytest.mark.parametrize("value, expected", [
    ("17/05/2025", date(2025, 5, 17)),
    ("01/01/2024", date(2024, 1, 1)),
    ("31/12/2023", date(2023, 12, 31)),
    ("2025-05-17", date(2025, 5, 17)),
    ("2024-01-01", date(2024, 1, 1)),
    ("2023-12-31", date(2023, 12, 31)),
])
def test_parse_date_valid(value, expected):
    assert _parse_date(value) == expected


@pytest.mark.parametrize("value", [
    "",
    "not-a-date",
    "32/01/2025",
    "2025/05/17",
    "17-05-2025",
])
def test_parse_date_invalid_raises(value):
    with pytest.raises(ValueError, match="Unrecognized date format"):
        _parse_date(value)


def test_parse_date_none_raises():
    with pytest.raises(AttributeError):
        _parse_date(None)
