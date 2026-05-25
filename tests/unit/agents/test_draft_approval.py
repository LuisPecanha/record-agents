"""Unit tests for pure functions in agents/draft_approval.py."""

import pytest

from agents.draft_approval import _is_pending, _is_approver_reply, _reply_is_approved


# ---------------------------------------------------------------------------
# _is_pending — identifies email_log rows that need approval processing
# ---------------------------------------------------------------------------

def test_is_pending_all_conditions_met():
    row = {"notification_sent": "TRUE", "aprovado": "FALSE", "enviado": "FALSE"}
    assert _is_pending(row) is True


@pytest.mark.parametrize("notification_sent", ["FALSE", "false", ""])
def test_is_pending_notification_not_sent(notification_sent):
    row = {"notification_sent": notification_sent, "aprovado": "FALSE", "enviado": "FALSE"}
    assert _is_pending(row) is False


@pytest.mark.parametrize("aprovado", ["TRUE", "true", "True"])
def test_is_pending_already_approved(aprovado):
    row = {"notification_sent": "TRUE", "aprovado": aprovado, "enviado": "FALSE"}
    assert _is_pending(row) is False


@pytest.mark.parametrize("enviado", ["TRUE", "true", "True"])
def test_is_pending_already_sent(enviado):
    row = {"notification_sent": "TRUE", "aprovado": "FALSE", "enviado": enviado}
    assert _is_pending(row) is False


def test_is_pending_boolean_values_from_gspread():
    # gspread sometimes returns Python booleans instead of strings
    row = {"notification_sent": True, "aprovado": False, "enviado": False}
    assert _is_pending(row) is True


def test_is_pending_boolean_true_aprovado_blocks():
    row = {"notification_sent": True, "aprovado": True, "enviado": False}
    assert _is_pending(row) is False


def test_is_pending_case_insensitive():
    row = {"notification_sent": "true", "aprovado": "false", "enviado": "false"}
    assert _is_pending(row) is True


def test_is_pending_missing_keys_returns_false():
    assert _is_pending({}) is False


def test_is_pending_whitespace_in_values():
    row = {"notification_sent": "  TRUE  ", "aprovado": "  FALSE  ", "enviado": "  FALSE  "}
    assert _is_pending(row) is True


# ---------------------------------------------------------------------------
# _is_approver_reply — sender check against the approver list
# ---------------------------------------------------------------------------

_APPROVERS = ["luis@balters.com", "admin@balters.com"]


def test_is_approver_reply_bare_email_match():
    reply = {"from": "luis@balters.com"}
    assert _is_approver_reply(reply, _APPROVERS) is True


def test_is_approver_reply_name_bracket_format():
    reply = {"from": "Luis <luis@balters.com>"}
    assert _is_approver_reply(reply, _APPROVERS) is True


def test_is_approver_reply_case_insensitive_sender():
    reply = {"from": "LUIS@BALTERS.COM"}
    assert _is_approver_reply(reply, _APPROVERS) is True


def test_is_approver_reply_case_insensitive_approver_list():
    reply = {"from": "luis@balters.com"}
    assert _is_approver_reply(reply, ["LUIS@BALTERS.COM"]) is True


def test_is_approver_reply_not_in_list():
    reply = {"from": "random@example.com"}
    assert _is_approver_reply(reply, _APPROVERS) is False


def test_is_approver_reply_empty_approver_list():
    reply = {"from": "luis@balters.com"}
    assert _is_approver_reply(reply, []) is False


def test_is_approver_reply_multiple_approvers_second_matches():
    reply = {"from": "admin@balters.com"}
    assert _is_approver_reply(reply, _APPROVERS) is True


def test_is_approver_reply_missing_from_key():
    assert _is_approver_reply({}, _APPROVERS) is False


# ---------------------------------------------------------------------------
# _reply_is_approved — approval keyword detection in reply body
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    "APROVADO",
    "aprovado",
    "Aprovado",
    "  APROVADO  ",       # leading/trailing whitespace
    "Sim, APROVADO.",     # embedded in a sentence
    "Olá, pode enviar. APROVADO\nObrigado.",  # in a longer body
    "aprovado!",          # with punctuation attached
])
def test_reply_is_approved_truthy_cases(body):
    assert _reply_is_approved({"body": body}) is True


@pytest.mark.parametrize("body", [
    "",
    "Recebido, aguardando.",
    "Ainda não tenho certeza.",
    "aprovei a resposta",   # "aprovei" does not contain "aprovado"
    "aprovação pendente",   # "aprovação" does not contain "aprovado"
    "REPROVADO",            # "aprovado" is NOT a substring of "reprovado" — safe
])
def test_reply_is_approved_falsy_cases(body):
    assert _reply_is_approved({"body": body}) is False


def test_reply_is_approved_reprovado_is_not_a_substring():
    # Confirms "aprovado" does not appear inside "reprovado" — REPROVADO cannot
    # accidentally trigger approval
    assert _reply_is_approved({"body": "REPROVADO"}) is False


def test_reply_is_approved_negation_also_matches():
    # "não aprovado" contains "aprovado" as a substring — documented behaviour
    assert _reply_is_approved({"body": "Não aprovado"}) is True


def test_reply_is_approved_missing_body_key():
    assert _reply_is_approved({}) is False


def test_reply_is_approved_none_body():
    # str(None) == "None", which does not contain "aprovado"
    assert _reply_is_approved({"body": None}) is False
