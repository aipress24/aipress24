"""Security service for password hashing and verification."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import hashlib
import os


def generate_password_hash(password: str) -> tuple[bytes, bytes]:
    """Generate a secure password hash with salt.

    Args:
        password: Plain text password to hash.

    Returns:
        tuple[bytes, bytes]: Salt and hashed key.
    """
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return salt, key


def check_password_hash(password: str, salt: bytes, key: bytes) -> bool:
    """Verify a password against a stored hash.

    Args:
        password: Plain text password to verify.
        salt: Salt used in original hash.
        key: Original hashed key to compare against.

    Returns:
        bool: True if password matches, False otherwise.
    """
    new_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return new_key == key
