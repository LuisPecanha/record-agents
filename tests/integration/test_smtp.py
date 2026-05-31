"""Integration tests: verifies SMTP connectivity via GmailClient (connection only, no email sent)."""

import os
import smtplib

import pytest

pytestmark = pytest.mark.integration


def test_gmail_client_initializes(gmail_client):
    assert gmail_client is not None


def test_smtp_connection():
    """Establish an SMTP_SSL connection and authenticate without sending any email."""
    email = os.getenv("BALTERS_EMAIL")
    password = os.getenv("GMAIL_APP_PASSWORD")
    assert email, "BALTERS_EMAIL not set"
    assert password, "GMAIL_APP_PASSWORD not set"

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(email, password)
        # login succeeds — connection confirmed, nothing sent
