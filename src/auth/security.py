"""
Password hashing and verification.

Uses PBKDF2-HMAC-SHA256 from the standard library so no additional native
dependency is required. Hashes are stored in a self-describing string so the
iteration count can be raised later without invalidating existing users.
"""

import hashlib
import hmac
import os
import secrets

from src.config import settings

# Format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 600_000
SALT_BYTES = 16
_SEPARATOR = "$"


def hash_password(password: str, *, iterations: int = DEFAULT_ITERATIONS) -> str:
    """Hash a password with a fresh random salt."""
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")

    salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return _SEPARATOR.join([ALGORITHM, str(iterations), salt.hex(), digest.hex()])


def verify_password(password: str, stored: str) -> bool:
    """
    Verify a password against a stored hash using a constant-time comparison.

    Returns False for malformed or empty inputs rather than raising, so callers
    cannot distinguish "no such user" from "bad hash" by exception behaviour.
    """
    if not password or not stored:
        return False

    try:
        algorithm, iterations_str, salt_hex, expected_hex = stored.split(_SEPARATOR)
        if algorithm != ALGORITHM:
            return False
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
    except (ValueError, AttributeError):
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


def needs_rehash(stored: str, *, iterations: int = DEFAULT_ITERATIONS) -> bool:
    """True if a stored hash uses an outdated algorithm or iteration count."""
    try:
        algorithm, iterations_str, _, _ = stored.split(_SEPARATOR)
    except (ValueError, AttributeError):
        return True
    return algorithm != ALGORITHM or int(iterations_str) < iterations


def generate_password(length: int = 20) -> str:
    """
    Generate a random password for bootstrap/reset flows.

    Guarantees at least one character from each required class so the result
    always satisfies ``validate_password_strength``; a purely random draw would
    occasionally omit one.
    """
    lowercase = "abcdefghijkmnopqrstuvwxyz"
    uppercase = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    symbols = "!@#%^&*-_"
    alphabet = lowercase + uppercase + digits + symbols

    length = max(length, settings.MIN_PASSWORD_LENGTH, 4)

    required = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(symbols),
    ]
    remainder = [secrets.choice(alphabet) for _ in range(length - len(required))]

    characters = required + remainder
    # Shuffle so the guaranteed characters are not always in the same positions.
    for i in range(len(characters) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        characters[i], characters[j] = characters[j], characters[i]

    return "".join(characters)


def validate_password_strength(password: str) -> list[str]:
    """Return a list of policy violations; empty means the password is acceptable."""
    problems: list[str] = []
    minimum = settings.MIN_PASSWORD_LENGTH

    if len(password or "") < minimum:
        problems.append(f"Password must be at least {minimum} characters long")
    if not any(c.islower() for c in password or ""):
        problems.append("Password must contain a lowercase letter")
    if not any(c.isupper() for c in password or ""):
        problems.append("Password must contain an uppercase letter")
    if not any(c.isdigit() for c in password or ""):
        problems.append("Password must contain a digit")

    return problems
