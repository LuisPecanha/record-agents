"""Unit tests for pure functions in agents/email_triage.py."""

import pytest

from agents.email_triage import (
    _parse_response,
    _reply_subject,
    _build_notification_body,
    _should_skip,
    _SKIP_PATTERNS,
)


# ---------------------------------------------------------------------------
# _parse_response — parses Claude's raw text into (classification, draft)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("category", ["DEMO", "IMPRENSA", "PARCERIA", "BOOKING", "OUTRO"])
def test_parse_response_all_valid_categories(category):
    text = f"CLASSIFICACAO: {category}\nRASCUNHO: Olá, obrigado pelo contato."
    classification, draft = _parse_response(text)
    assert classification == category
    assert "Olá, obrigado pelo contato." in draft


def test_parse_response_strips_whitespace_around_category():
    text = "CLASSIFICACAO:   DEMO   \nRASCUNHO: body"
    classification, _ = _parse_response(text)
    assert classification == "DEMO"


def test_parse_response_unknown_category_returned_as_is():
    text = "CLASSIFICACAO: SPAM\nRASCUNHO: body"
    classification, _ = _parse_response(text)
    assert classification == "SPAM"


def test_parse_response_empty_classification_when_line_missing():
    text = "RASCUNHO: some body text"
    classification, draft = _parse_response(text)
    assert classification == ""
    assert "some body text" in draft


def test_parse_response_empty_draft_when_rascunho_missing():
    text = "CLASSIFICACAO: DEMO"
    classification, draft = _parse_response(text)
    assert classification == "DEMO"
    assert draft == ""


def test_parse_response_multiline_draft_preserved():
    text = "CLASSIFICACAO: IMPRENSA\nRASCUNHO: Linha 1\nLinha 2\nLinha 3"
    _, draft = _parse_response(text)
    assert "Linha 1" in draft
    assert "Linha 2" in draft
    assert "Linha 3" in draft


def test_parse_response_draft_is_everything_after_rascunho_marker():
    # RASCUNHO is split on the entire text, so leading whitespace is stripped
    text = "CLASSIFICACAO: OUTRO\nRASCUNHO:\n\nPrimeira linha real"
    _, draft = _parse_response(text)
    assert "Primeira linha real" in draft


def test_parse_response_classificacao_colon_without_space_not_matched():
    # "CLASSIFICACAO : DEMO" has a space before the colon — not recognised
    text = "CLASSIFICACAO : DEMO\nRASCUNHO: body"
    classification, _ = _parse_response(text)
    assert classification == ""


def test_parse_response_returns_two_strings():
    classification, draft = _parse_response("CLASSIFICACAO: DEMO\nRASCUNHO: ok")
    assert isinstance(classification, str)
    assert isinstance(draft, str)


# ---------------------------------------------------------------------------
# _reply_subject — ensures "Re:" prefix on outgoing reply subject
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("subject, expected", [
    ("Demo submission",        "Re: Demo submission"),
    ("Parceria com a Balters", "Re: Parceria com a Balters"),
    ("",                       "Re: "),
])
def test_reply_subject_adds_prefix(subject, expected):
    assert _reply_subject(subject) == expected


@pytest.mark.parametrize("already_prefixed", [
    "Re: something",
    "re: something",
    "RE: something",
    "Re:something",   # no space after colon — still starts with "re:"
])
def test_reply_subject_does_not_double_prefix(already_prefixed):
    assert _reply_subject(already_prefixed) == already_prefixed


# ---------------------------------------------------------------------------
# _build_notification_body — builds the approval-request email body
# ---------------------------------------------------------------------------

def test_build_notification_body_contains_all_fields():
    body = _build_notification_body(
        from_field="DJ Balters <dj@balters.com>",
        subject="Demo track",
        classification="DEMO",
        draft="Olá DJ Balters, recebemos sua demo.",
    )
    assert "DJ Balters <dj@balters.com>" in body
    assert "Demo track" in body
    assert "DEMO" in body
    assert "Olá DJ Balters, recebemos sua demo." in body


def test_build_notification_body_contains_aprovado_prompt():
    body = _build_notification_body("a@b.com", "subj", "OUTRO", "draft")
    assert "APROVADO" in body


def test_build_notification_body_contains_separator():
    body = _build_notification_body("a@b.com", "subj", "OUTRO", "draft")
    assert "-" * 10 in body  # at least 10 dashes (separator line)


def test_build_notification_body_returns_str():
    result = _build_notification_body("a@b.com", "s", "DEMO", "d")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _should_skip — sender-based automated-sender filter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pattern", _SKIP_PATTERNS)
def test_should_skip_each_pattern(pattern):
    assert _should_skip(f"sender@{pattern}.com") is True


@pytest.mark.parametrize("from_field", [
    "no-reply@service.com",
    "noreply@notifications.com",
    "update@accounts.google.com",
    "team@googlecommunityteam.com",
])
def test_should_skip_known_automated_senders(from_field):
    assert _should_skip(from_field) is True


def test_should_skip_is_case_insensitive():
    assert _should_skip("NO-REPLY@service.com") is True
    assert _should_skip("NoReply@service.com") is True


def test_should_skip_pattern_anywhere_in_from_field():
    # pattern embedded in display name or domain
    assert _should_skip("Notifications <no-reply@example.com>") is True


@pytest.mark.parametrize("from_field", [
    "demo@artist.com",
    "info@balters.com",
    "booking@venue.com",
    "press@magazine.com",
    "",
])
def test_should_not_skip_real_senders(from_field):
    assert _should_skip(from_field) is False
