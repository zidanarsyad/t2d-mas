"""Small, deterministic PII masking helpers for locally stored ticket text."""
from __future__ import annotations

import re
from typing import Any


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d().\s-]{7,}\d)(?!\w)")
TOKEN_RE = re.compile(r"(?i)\b(?:bearer\s+\S+|(?:api[_-]?key|access[_-]?token|secret|token)\s*[:=]\s*\S+)")
MIN_PHONE_DIGITS = 9  # dates ("2026-10-14") and short numbers have fewer digits


def _mask_phone(match: re.Match[str]) -> str:
    digits = sum(character.isdigit() for character in match.group(0))
    return "<PHONE>" if digits >= MIN_PHONE_DIGITS else match.group(0)


def mask_with_counts(value: Any) -> tuple[str, dict[str, int]]:
    """Mask emails, phone numbers and tokens, and report how many of each were found."""
    text = str(value or "")
    text, emails = EMAIL_RE.subn("<EMAIL>", text)
    before = text.count("<PHONE>")
    text = PHONE_RE.sub(_mask_phone, text)
    phones = text.count("<PHONE>") - before
    text, tokens = TOKEN_RE.subn("<TOKEN>", text)
    return text, {"emails": emails, "phones": phones, "tokens": tokens}


def mask_text(value: Any) -> str:
    """Mask common email, phone, and token patterns before persistence."""
    return mask_with_counts(value)[0]


def mask_value(value: Any) -> Any:
    """Apply text masking recursively while preserving JSON-shaped values."""
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return {str(key): mask_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [mask_value(item) for item in value]
    return value
