"""
Password hashing and token generation/hashing primitives.

Design choices (see PRODUCT_READINESS_AUDIT.md Section 3-4 and the README's
Authentication Architecture section for the full rationale):
- Passwords are hashed with Argon2 (via argon2-cffi), never stored plaintext
  or with a reversible cipher, and never hashed with a custom algorithm.
- Session and password-reset tokens are cryptographically random opaque
  strings. Only a SHA-256 hash of each token is ever persisted; the raw
  token exists only in the client's cookie (session) or the one-time email
  link (reset), and is never recoverable from the database.
"""
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash

_password_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, InvalidHash):
        return False


def normalize_email(email: str) -> str:
    """Lowercase + strip so 'User@Example.com' and 'user@example.com' collide correctly."""
    return email.strip().lower()


def generate_opaque_token() -> str:
    """A cryptographically random, URL-safe token (used for sessions and password resets)."""
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    """One-way hash of an opaque token for safe storage (never the raw token)."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
