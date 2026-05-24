"""Shared utilities for integrations."""

import re


def _extract_email(from_field: str) -> str:
    match = re.search(r"<(.+?)>", from_field)
    if match:
        return match.group(1).strip()
    return from_field.strip()
