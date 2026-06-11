"""Security utilities — sensitive field detection and masking."""
import re
import json
from pathlib import Path

# Patterns that indicate sensitive values
SENSITIVE_PATTERNS = re.compile(
    r'('
    r'(?i)api[_-]?key|'
    r'(?i)auth[_-]?token|'
    r'(?i)access[_-]?token|'
    r'(?i)secret[_-]?key|'
    r'(?i)private[_-]?key|'
    r'(?i)client[_-]?secret|'
    r'(?i)password|'
    r'(?i)passwd|'
    r'(?i)token[_-]?'
    r')',
    re.IGNORECASE
)

# Patterns for values that look like secrets
SECRET_VALUE_PATTERNS = re.compile(
    r'(sk-[a-zA-Z0-9]{20,})|'       # OpenAI/Anthropic API key style
    r'(gh[pousr]_[a-zA-Z0-9]{20,})|'
    r'([a-f0-9]{32,})|'              # MD5+ length hex
    r'(eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,})',  # JWT
    re.IGNORECASE
)

MASK = "****"


def is_sensitive_key(key: str) -> bool:
    """Check if a key name looks like a sensitive field."""
    return bool(SENSITIVE_PATTERNS.search(key))


def is_sensitive_value(value: str) -> bool:
    """Check if a value looks like a secret/token/key."""
    if not value or not isinstance(value, str):
        return False
    return bool(SECRET_VALUE_PATTERNS.search(value))


def mask_value(value: str) -> str:
    """Mask a sensitive value for display."""
    if not value or not isinstance(value, str):
        return str(value) if value is not None else ""
    if len(value) <= 8:
        return MASK
    return value[:4] + MASK + value[-4:]


def mask_dict(d: dict) -> dict:
    """Return a copy of dict with sensitive values masked."""
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = mask_dict(v)
        elif isinstance(v, list):
            result[k] = _mask_list(v)
        elif isinstance(v, str) and is_sensitive_key(k):
            result[k] = mask_value(v)
        elif isinstance(v, str) and is_sensitive_value(v):
            result[k] = mask_value(v)
        else:
            result[k] = v
    return result


def _mask_list(lst: list) -> list:
    return [mask_dict(item) if isinstance(item, dict) else item for item in lst]


def mask_json_file(path: Path) -> dict:
    """Read a JSON file and return its content with sensitive fields masked."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return mask_dict(data)
    except (json.JSONDecodeError, OSError):
        return {}
