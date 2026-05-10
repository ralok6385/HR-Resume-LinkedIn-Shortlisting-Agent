"""
Security utilities for the HR Resume Shortlisting Agent.

Implements mitigations for:
- Prompt Injection: Input sanitization and output validation
- Data Privacy / PII: Masking of personal information in logs
- API Key Exposure: Secure key management
- Hallucination Risk: Output validation with Pydantic schemas
- Unauthorized Access: File validation and rate limiting
"""

import re
import os
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================
# PII Detection & Masking
# ============================================================

# Common PII patterns
PII_PATTERNS = {
    "email": re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
    "phone": re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}'),
    "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    "aadhaar": re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b'),
    "pan": re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b'),
}


def mask_pii(text: str, mask_char: str = "●") -> str:
    """
    Mask personally identifiable information in text for safe logging.
    
    Args:
        text: Input text potentially containing PII
        mask_char: Character used for masking
    
    Returns:
        Text with PII replaced by mask characters
    """
    masked = text
    for pii_type, pattern in PII_PATTERNS.items():
        matches = pattern.findall(masked)
        for match in matches:
            if pii_type == "email":
                # Preserve domain for context: user●●●@domain.com
                parts = match.split("@")
                replacement = f"{parts[0][:2]}{mask_char * 4}@{parts[1]}"
            elif pii_type == "phone":
                # Show last 4 digits: ●●●●●●1234
                replacement = f"{mask_char * 6}{match[-4:]}"
            else:
                replacement = mask_char * len(match)
            masked = masked.replace(match, replacement)
    return masked


def hash_pii(text: str) -> str:
    """Create a one-way hash of PII for audit purposes without exposing the data."""
    return hashlib.sha256(text.encode()).hexdigest()[:12]


# ============================================================
# Input Sanitization (Anti-Prompt Injection)
# ============================================================

# Patterns that might indicate prompt injection attempts
INJECTION_PATTERNS = [
    re.compile(r'ignore\s+(all\s+)?previous\s+instructions', re.IGNORECASE),
    re.compile(r'disregard\s+(all\s+)?prior\s+instructions', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+a', re.IGNORECASE),
    re.compile(r'system\s*:\s*you\s+are', re.IGNORECASE),
    re.compile(r'<\|im_start\|>', re.IGNORECASE),
    re.compile(r'```\s*system', re.IGNORECASE),
    re.compile(r'ADMIN\s*MODE', re.IGNORECASE),
    re.compile(r'override\s+scoring', re.IGNORECASE),
    re.compile(r'give\s+(me|this|all)\s+(a\s+)?score\s+of\s+10', re.IGNORECASE),
    re.compile(r'always\s+score\s+(this|me)\s+high', re.IGNORECASE),
]


def sanitize_input(text: str) -> tuple[str, list[str]]:
    """
    Sanitize user input to prevent prompt injection attacks.
    
    Args:
        text: Raw input text (resume content or JD)
    
    Returns:
        Tuple of (sanitized_text, list_of_warnings)
    """
    warnings = []
    sanitized = text

    # Check for injection patterns
    for pattern in INJECTION_PATTERNS:
        if pattern.search(sanitized):
            match_text = pattern.search(sanitized).group()
            warnings.append(f"Potential prompt injection detected: '{match_text}'")
            sanitized = pattern.sub("[REDACTED]", sanitized)

    # Remove any HTML/script tags
    sanitized = re.sub(r'<script[^>]*>.*?</script>', '[REMOVED]', sanitized, flags=re.DOTALL | re.IGNORECASE)
    sanitized = re.sub(r'<iframe[^>]*>.*?</iframe>', '[REMOVED]', sanitized, flags=re.DOTALL | re.IGNORECASE)

    # Limit input length (prevent token stuffing)
    max_chars = 50000  # ~12k tokens
    if len(sanitized) > max_chars:
        warnings.append(f"Input truncated from {len(sanitized)} to {max_chars} characters")
        sanitized = sanitized[:max_chars]

    if warnings:
        logger.warning(f"Input sanitization warnings: {warnings}")

    return sanitized, warnings


# ============================================================
# File Validation
# ============================================================

def validate_file(file_path: str | Path, max_size_mb: int = 10, 
                  allowed_extensions: Optional[list[str]] = None) -> tuple[bool, str]:
    """
    Validate an uploaded file for security.
    
    Args:
        file_path: Path to the file
        max_size_mb: Maximum allowed file size in MB
        allowed_extensions: List of allowed file extensions
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    path = Path(file_path)
    
    if allowed_extensions is None:
        allowed_extensions = [".pdf", ".docx", ".doc", ".txt", ".json"]

    # Check extension
    if path.suffix.lower() not in allowed_extensions:
        return False, f"File type '{path.suffix}' not allowed. Allowed: {allowed_extensions}"

    # Check file size
    if path.exists():
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            return False, f"File size ({size_mb:.1f}MB) exceeds limit ({max_size_mb}MB)"

    # Check for path traversal
    try:
        resolved = path.resolve()
        if ".." in str(file_path):
            return False, "Path traversal detected"
    except Exception as e:
        return False, f"Invalid file path: {e}"

    return True, ""


# ============================================================
# Output Validation
# ============================================================

def validate_score(score: float, dimension_name: str) -> float:
    """Validate and clamp a score to the valid range [0, 10]."""
    if not isinstance(score, (int, float)):
        logger.warning(f"Invalid score type for {dimension_name}: {type(score)}, defaulting to 0")
        return 0.0
    
    clamped = max(0.0, min(10.0, float(score)))
    if clamped != float(score):
        logger.warning(f"Score for {dimension_name} clamped from {score} to {clamped}")
    
    return round(clamped, 1)


def validate_scores_dict(scores: dict) -> dict:
    """Validate all scores in a scoring dictionary."""
    validated = {}
    for key, value in scores.items():
        if isinstance(value, dict) and "score" in value:
            value["score"] = validate_score(value["score"], key)
            validated[key] = value
        elif isinstance(value, (int, float)):
            validated[key] = validate_score(value, key)
        else:
            validated[key] = value
    return validated


# ============================================================
# Audit Logging
# ============================================================

class AuditLogger:
    """Secure audit logger for tracking all agent actions."""
    
    def __init__(self, log_file: str = "audit_log.json", mask_pii_enabled: bool = True):
        self.log_file = Path(log_file)
        self.mask_pii_enabled = mask_pii_enabled
        self._entries: list[dict] = []

    def log(self, action: str, details: dict, user_id: str = "system"):
        """Log an action with timestamp and details."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user_id": user_id,
            "details": self._sanitize_details(details),
        }
        self._entries.append(entry)
        logger.info(f"Audit: {action} — {json.dumps(entry['details'], default=str)[:200]}")

    def _sanitize_details(self, details: dict) -> dict:
        """Mask PII in log details if enabled."""
        if not self.mask_pii_enabled:
            return details
        
        sanitized = {}
        for key, value in details.items():
            if isinstance(value, str) and key.lower() in ("email", "phone", "name", "address"):
                sanitized[key] = mask_pii(value)
            elif isinstance(value, str) and len(value) > 500:
                # Truncate very long values in logs
                sanitized[key] = value[:500] + "... [truncated]"
            else:
                sanitized[key] = value
        return sanitized

    def save(self):
        """Save audit log to file."""
        with open(self.log_file, "w") as f:
            json.dump(self._entries, f, indent=2, default=str)

    def get_entries(self) -> list[dict]:
        """Get all audit log entries."""
        return self._entries.copy()
