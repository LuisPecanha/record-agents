"""Unit tests for _compute_deadlines() in agents/release_calendar.py."""

import pytest
from datetime import date, timedelta

from agents.release_calendar import _compute_deadlines, _DEADLINES


RELEASE_DATE = date(2025, 8, 1)  # Friday


@pytest.mark.parametrize("stage, offset", _DEADLINES)
def test_deadline_offset(stage, offset):
    deadlines = _compute_deadlines(RELEASE_DATE)
    entry = next(d for d in deadlines if d["etapa"] == stage)
    assert entry["_date"] == RELEASE_DATE + timedelta(days=offset)


def test_deadline_count():
    deadlines = _compute_deadlines(RELEASE_DATE)
    assert len(deadlines) == 8


def test_deadline_formatted_string_matches_date():
    deadlines = _compute_deadlines(RELEASE_DATE)
    for d in deadlines:
        assert d["deadline"] == d["_date"].strftime("%d/%m/%Y")


def test_deadline_artist_and_track_propagated():
    deadlines = _compute_deadlines(RELEASE_DATE, artist="DJ Teste", track="Track X")
    for d in deadlines:
        assert d["artista"] == "DJ Teste"
        assert d["titulo"] == "Track X"


def test_weekend_release_date_pure_arithmetic():
    # Saturday release — no weekend adjustment, dates land wherever the math puts them
    saturday = date(2025, 6, 28)  # weekday() == 5
    assert saturday.weekday() == 5

    deadlines = _compute_deadlines(saturday)

    # -42 days from Saturday is also a Saturday
    aprovacao = next(d for d in deadlines if d["etapa"] == "Aprovação final da track")
    assert aprovacao["_date"] == date(2025, 5, 17)
    assert aprovacao["_date"].weekday() == 5  # still Saturday

    # -3 days from Saturday is Wednesday
    posts = next(d for d in deadlines if d["etapa"] == "Posts agendados nas redes")
    assert posts["_date"] == date(2025, 6, 25)
    assert posts["_date"].weekday() == 2  # Wednesday


def test_past_release_date_produces_past_deadlines():
    past_release = date(2024, 1, 10)
    deadlines = _compute_deadlines(past_release)
    today = date.today()
    for d in deadlines:
        assert d["_date"] < today
