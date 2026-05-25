"""Unit tests for pure functions in agents/press_kit.py."""

import pytest

from agents.press_kit import (
    _build_release_data,
    _parse_blocks,
    _format_file_content,
    _build_filename,
)


# ---------------------------------------------------------------------------
# _build_release_data — assembles sheet row into a formatted string
# ---------------------------------------------------------------------------

def _full_row():
    return {
        "nome_artista":    "DJ Balters",
        "titulo_track":    "Midnight Drive",
        "genero":          "Afro House",
        "data_lancamento": "17/05/2025",
        "descricao":       "Uma jornada sonora.",
        "link_track":      "https://soundcloud.com/djbalters/midnight-drive",
        "link_perfil":     "https://soundcloud.com/djbalters",
    }


def test_build_release_data_all_fields_present():
    result = _build_release_data(_full_row())
    assert "DJ Balters" in result
    assert "Midnight Drive" in result
    assert "Afro House" in result
    assert "17/05/2025" in result
    assert "Uma jornada sonora." in result
    assert "https://soundcloud.com/djbalters/midnight-drive" in result
    assert "https://soundcloud.com/djbalters" in result


def test_build_release_data_label_colon_value_format():
    result = _build_release_data(_full_row())
    assert "Artista: DJ Balters" in result
    assert "Título: Midnight Drive" in result
    assert "Gênero: Afro House" in result


def test_build_release_data_empty_field_omitted():
    row = _full_row()
    row["descricao"] = ""
    result = _build_release_data(row)
    assert "Descrição" not in result
    assert "DJ Balters" in result  # other fields still present


def test_build_release_data_whitespace_only_field_omitted():
    row = _full_row()
    row["link_perfil"] = "   "
    result = _build_release_data(row)
    assert "Link do perfil" not in result


def test_build_release_data_all_empty_returns_empty_string():
    row = {k: "" for k in _full_row()}
    assert _build_release_data(row) == ""


def test_build_release_data_missing_keys_omitted():
    result = _build_release_data({})
    assert result == ""


def test_build_release_data_returns_str():
    assert isinstance(_build_release_data(_full_row()), str)


# ---------------------------------------------------------------------------
# _parse_blocks — splits Claude's === delimited response into three blocks
# ---------------------------------------------------------------------------

_CLEAN_RESPONSE = (
    "=== PRESS KIT BLURB ===\n"
    "Midnight Drive é o novo single de DJ Balters.\n"
    "=== RELEASE NOTES ===\n"
    "Disponível em todas as plataformas em 17/05/2025.\n"
    "=== SOCIAL CAPTION ===\n"
    "🎵 Midnight Drive está fora! #AgroHouse"
)


def test_parse_blocks_clean_response():
    blurb, notes, caption = _parse_blocks(_CLEAN_RESPONSE)
    assert "Midnight Drive é o novo single" in blurb
    assert "Disponível em todas as plataformas" in notes
    assert "Midnight Drive está fora!" in caption


def test_parse_blocks_strips_leading_trailing_whitespace():
    text = (
        "=== PRESS KIT BLURB ===\n\n  conteúdo com espaços  \n\n"
        "=== RELEASE NOTES ===\nnotes\n"
        "=== SOCIAL CAPTION ===\ncaption\n"
    )
    blurb, _, _ = _parse_blocks(text)
    assert blurb == "conteúdo com espaços"


def test_parse_blocks_multiline_content_preserved():
    text = (
        "=== PRESS KIT BLURB ===\n"
        "Linha 1\nLinha 2\nLinha 3\n"
        "=== RELEASE NOTES ===\nnotes\n"
        "=== SOCIAL CAPTION ===\ncaption\n"
    )
    blurb, _, _ = _parse_blocks(text)
    assert "Linha 1" in blurb
    assert "Linha 2" in blurb
    assert "Linha 3" in blurb


def test_parse_blocks_missing_section_returns_empty_string():
    text = (
        "=== PRESS KIT BLURB ===\nblurb content\n"
        "=== SOCIAL CAPTION ===\ncaption content\n"
    )
    blurb, notes, caption = _parse_blocks(text)
    assert blurb == "blurb content"
    assert notes == ""
    assert caption == "caption content"


def test_parse_blocks_all_sections_missing():
    blurb, notes, caption = _parse_blocks("Some text with no delimiters at all.")
    assert blurb == ""
    assert notes == ""
    assert caption == ""


def test_parse_blocks_empty_string_input():
    blurb, notes, caption = _parse_blocks("")
    assert blurb == ""
    assert notes == ""
    assert caption == ""


def test_parse_blocks_only_delimiters_no_content():
    text = "=== PRESS KIT BLURB ===\n=== RELEASE NOTES ===\n=== SOCIAL CAPTION ==="
    blurb, notes, caption = _parse_blocks(text)
    # headers follow immediately with no content between them — all empty
    assert blurb == ""
    assert notes == ""
    assert caption == ""


def test_parse_blocks_extra_whitespace_around_header_tokens():
    # extra spaces between === and the header name are stripped — header is still recognised
    text = (
        "===  PRESS KIT BLURB  ===\nblurb content\n"
        "===  RELEASE NOTES  ===\nnotes content\n"
        "===  SOCIAL CAPTION  ===\ncaption content\n"
    )
    blurb, notes, caption = _parse_blocks(text)
    assert blurb == "blurb content"
    assert notes == "notes content"
    assert caption == "caption content"


def test_parse_blocks_returns_three_strings():
    result = _parse_blocks(_CLEAN_RESPONSE)
    assert len(result) == 3
    assert all(isinstance(s, str) for s in result)


# ---------------------------------------------------------------------------
# _format_file_content — assembles the .txt file body from three blocks
# ---------------------------------------------------------------------------

def test_format_file_content_contains_all_three_blocks():
    result = _format_file_content("blurb text", "notes text", "caption text")
    assert "blurb text" in result
    assert "notes text" in result
    assert "caption text" in result


def test_format_file_content_contains_section_headers():
    result = _format_file_content("b", "n", "c")
    assert "PRESS KIT BLURB" in result
    assert "RELEASE NOTES" in result
    assert "SOCIAL CAPTION" in result


def test_format_file_content_has_separator_lines():
    result = _format_file_content("b", "n", "c")
    assert "=" * 60 in result


def test_format_file_content_blocks_appear_in_order():
    result = _format_file_content("BLURB_CONTENT", "NOTES_CONTENT", "CAPTION_CONTENT")
    blurb_pos = result.index("BLURB_CONTENT")
    notes_pos = result.index("NOTES_CONTENT")
    caption_pos = result.index("CAPTION_CONTENT")
    assert blurb_pos < notes_pos < caption_pos


def test_format_file_content_returns_str():
    assert isinstance(_format_file_content("a", "b", "c"), str)


# ---------------------------------------------------------------------------
# _build_filename — sanitizes artist/track/date into a safe .txt filename
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nome, titulo, data, expected", [
    ("DJ Balters", "Midnight Drive", "17/05/2025",
     "dj_balters_midnight_drive_17-05-2025.txt"),
    ("Artist", "Track", "2025-05-17",
     "artist_track_2025-05-17.txt"),
    # spaces become underscores, slashes become hyphens, all lowercase
    ("My Artist", "A Track", "01/01/2024",
     "my_artist_a_track_01-01-2024.txt"),
    # already lowercase, no spaces
    ("dj", "track", "2024-06-01",
     "dj_track_2024-06-01.txt"),
])
def test_build_filename(nome, titulo, data, expected):
    assert _build_filename(nome, titulo, data) == expected


def test_build_filename_ends_with_txt():
    result = _build_filename("a", "b", "c")
    assert result.endswith(".txt")


def test_build_filename_no_spaces():
    result = _build_filename("DJ Name", "Track Title", "17/05/2025")
    assert " " not in result


def test_build_filename_all_lowercase():
    result = _build_filename("UPPERCASE", "TITLE", "2025-01-01")
    assert result == result.lower()
