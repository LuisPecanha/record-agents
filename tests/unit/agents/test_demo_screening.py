"""Unit tests for _evaluate_submission() in agents/demo_screening.py."""

import pytest

from agents.demo_screening import _evaluate_submission


_NOME = "DJ Balters"
_LINK = "https://soundcloud.com/djbalters/track"


# ---------------------------------------------------------------------------
# Core cases — all required scenarios
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nome_artistico, genero, link_track, expected_resultado, motivo_fragment", [
    # passes all criteria
    (_NOME, "House",         _LINK, "APROVADO",   None),
    (_NOME, "Indie Dance",   _LINK, "APROVADO",   None),
    (_NOME, "Afro House",    _LINK, "APROVADO",   None),
    (_NOME, "Melodic House", _LINK, "APROVADO",   None),
    (_NOME, "Tech House",    _LINK, "APROVADO",   None),
    # genre mismatch
    (_NOME, "Techno",        _LINK, "REPROVADO",  "escopo"),
    (_NOME, "Trance",        _LINK, "REPROVADO",  "escopo"),
    (_NOME, "Pop",           _LINK, "REPROVADO",  "escopo"),
    (_NOME, "Hip Hop",       _LINK, "REPROVADO",  "escopo"),
    (_NOME, "Funk",          _LINK, "REPROVADO",  "escopo"),
    (_NOME, "Sertanejo",     _LINK, "REPROVADO",  "escopo"),
    # incomplete form — missing nome_artistico
    ("",    "House",         _LINK, "INCOMPLETO", "nome artístico"),
    # missing digital presence — empty link_track
    (_NOME, "House",         "",    "INCOMPLETO", "link da track"),
    # multiple criteria fail: missing nome AND rejected genre (nome check is first)
    ("",    "Funk",          "",    "INCOMPLETO", "nome artístico"),
])
def test_evaluate_submission(nome_artistico, genero, link_track, expected_resultado, motivo_fragment):
    resultado, motivo = _evaluate_submission(nome_artistico, genero, link_track)
    assert resultado == expected_resultado
    if motivo_fragment:
        assert motivo_fragment in motivo


# ---------------------------------------------------------------------------
# Focused edge-case tests
# ---------------------------------------------------------------------------

def test_genre_check_is_case_insensitive():
    resultado, _ = _evaluate_submission(_NOME, "FUNK", _LINK)
    assert resultado == "REPROVADO"

    resultado, _ = _evaluate_submission(_NOME, "house", _LINK)
    assert resultado == "APROVADO"


def test_unknown_genre_defaults_to_aprovado():
    # Genuinely ambiguous genre — prompt says "em caso de dúvida, APROVADO"
    resultado, _ = _evaluate_submission(_NOME, "Minimal Deep Tech", _LINK)
    assert resultado == "APROVADO"


def test_missing_link_takes_precedence_over_rejected_genre():
    # Both link_track and genre fail; link check fires before genre check
    resultado, motivo = _evaluate_submission(_NOME, "Funk", "")
    assert resultado == "INCOMPLETO"
    assert "link da track" in motivo


def test_evaluate_submission_returns_two_strings():
    resultado, motivo = _evaluate_submission(_NOME, "House", _LINK)
    assert isinstance(resultado, str)
    assert isinstance(motivo, str)
