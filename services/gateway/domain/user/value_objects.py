"""Value objects for the User domain."""
from __future__ import annotations


class Email(str):
    """Normalized, validated e-mail address."""

    def __new__(cls, value: str) -> "Email":
        normalized = value.strip().lower()
        if "@" not in normalized or "." not in normalized.split("@")[-1]:
            raise ValueError(f"Invalid e-mail address: {value!r}")
        return super().__new__(cls, normalized)


class Username(str):
    """Normalized username — lowercase, stripped, min 3 chars."""

    def __new__(cls, value: str) -> "Username":
        normalized = value.strip().lower()
        if len(normalized) < 3:
            raise ValueError("Username must be at least 3 characters long.")
        return super().__new__(cls, normalized)


class PasswordHash(str):
    """Opaque wrapper for a bcrypt password hash — never exposed in responses."""

    def __new__(cls, value: str) -> "PasswordHash":
        return super().__new__(cls, value)
