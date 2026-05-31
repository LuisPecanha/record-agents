"""Integration tests: verifies SheetsClient can connect and read all expected tabs."""

import pytest
from integrations.sheets_client import (
    SHEET_DEADLINES,
    SHEET_DEMOS,
    SHEET_EMAIL_LOG,
    SHEET_LANCAMENTOS,
)

pytestmark = pytest.mark.integration


def test_sheets_client_initializes(sheets_client):
    assert sheets_client is not None


@pytest.mark.parametrize("tab,anchor", [
    (SHEET_LANCAMENTOS, "nome_artista"),
    (SHEET_DEADLINES, "artista"),
    (SHEET_EMAIL_LOG, "remetente"),
    (SHEET_DEMOS, "nome_artistico"),
])
def test_sheets_tab_readable(sheets_client, tab, anchor):
    rows = sheets_client.get_rows(tab, anchor=anchor)
    assert isinstance(rows, list)
