"""
Shared utilities for data ingestion operations.
"""
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def sanitize_text(text: str) -> str:
    """
    Sanitize text to remove null characters and invalid Unicode sequences
    that can cause database insertion errors.
    """
    if not text:
        return text

    # Remove null characters (\x00) - this is the main culprit
    text = text.replace('\x00', '')

    # Remove other problematic control characters but keep newlines and tabs
    text = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Handle invalid UTF-8 sequences by encoding and decoding
    try:
        # Encode to bytes and decode back to remove invalid sequences
        text = text.encode('utf-8', errors='replace').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        logger.warning("Failed to sanitize text encoding, falling back to ASCII")
        text = text.encode('ascii', errors='replace').decode('ascii')

    return text


def sanitize_metadata(metadata: Any) -> Any:
    """
    Recursively sanitize all string values in metadata to prevent JSON serialization issues.
    Handles dictionaries, lists, and nested structures.
    """
    if isinstance(metadata, dict):
        sanitized = {}
        for key, value in metadata.items():
            if isinstance(value, str):
                sanitized[key] = sanitize_text(value)
            elif isinstance(value, (dict, list)):
                sanitized[key] = sanitize_metadata(value)
            else:
                sanitized[key] = value
        return sanitized
    elif isinstance(metadata, list):
        return [
            sanitize_text(item) if isinstance(item, str) else sanitize_metadata(item)
            for item in metadata
        ]
    else:
        return metadata