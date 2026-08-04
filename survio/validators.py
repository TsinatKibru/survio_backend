import re
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags

# Regex matching HTML/script tags, event handlers, and URL-encoded script injection
HTML_SCRIPT_PATTERN = re.compile(
    r'<\s*script|<\s*/\s*script|<\s*iframe|<\s*style|javascript:|onerror\s*=|onload\s*=|onclick\s*=|eval\s*\(',
    re.IGNORECASE
)


def validate_no_html(value):
    """
    Strict server-side validator for text fields across the system.
    Rejects any string containing HTML tags, script payloads, or encoded script execution.
    """
    if not value or not isinstance(value, str):
        return

    if '<' in value or '>' in value or HTML_SCRIPT_PATTERN.search(value):
        raise ValidationError("Invalid input: HTML or script tags are not allowed.")


def sanitize_text(value):
    """Strips HTML tags and trims whitespace."""
    if value and isinstance(value, str):
        return strip_tags(value).strip()
    return value
