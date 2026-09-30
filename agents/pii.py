"""Small, deterministic PII masking helpers for locally stored ticket text."""
from __future__ import annotations

import re
from typing import Any


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d().\s-]{7,}\d)(?!\w)")
TOKEN_RE = re.compile(r"(?i)\b(?:bearer\s+\S+|(?:api[_-]?key|access[_-]?token|secret|token)\s*[:=]\s*\S+)")


def mask_text(value: Any) -> str:
    """Mask common email, phone, and token patterns before persistence."""
    text = str(value or "")
    text = EMAIL_RE.sub("<EMAIL>", text)
    text = PHONE_RE.sub("<PHONE>", text)
    return TOKEN_RE.sub("<TOKEN>", text)


def mask_value(value: Any) -> Any:
    """Apply text masking recursively while preserving JSON-shaped values."""
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return {str(key): mask_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [mask_value(item) for item in value]
    return value
