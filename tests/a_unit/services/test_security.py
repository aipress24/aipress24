# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for services/security module."""

from __future__ import annotations

from app.services.security import check_password_hash, generate_password_hash


class TestGeneratePasswordHash:
    """Test suite for generate_password_hash function."""

    def test_generate_password_hash_returns_tuple(self):
        """Test that generate_password_hash returns a tuple of salt and key."""
        password = "test_password"
        salt, key = generate_password_hash(password)

        assert isinstance(salt, bytes)
        assert isinstance(key, bytes)
        assert len(salt) == 32  # os.urandom(32)
        assert len(key) > 0

    def test_generate_password_hash_unique_salts(self):
        """Test that each call generates a unique salt."""
        password = "test_password"
        salt1, key1 = generate_password_hash(password)
        salt2, key2 = generate_password_hash(password)

        # Same password but different salts should produce different keys
        assert salt1 != salt2
        assert key1 != key2

    def test_generate_password_hash_different_passwords(self):
        """Test that different passwords produce different hashes."""
        salt1, key1 = generate_password_hash("password1")
        salt2, key2 = generate_password_hash("password2")

        assert key1 != key2


class TestCheckPasswordHash:
    """Test suite for check_password_hash function."""

    def test_check_password_hash_correct_password(self):
        """Test verification with correct password."""
        password = "my_secure_password"
        salt, key = generate_password_hash(password)

        assert check_password_hash(password, salt, key) is True

    def test_check_password_hash_incorrect_password(self):
        """Test verification with incorrect password."""
        password = "correct_password"
        salt, key = generate_password_hash(password)

        assert check_password_hash("wrong_password", salt, key) is False

    def test_check_password_hash_case_sensitive(self):
        """Test that password verification is case-sensitive."""
        password = "Password123"
        salt, key = generate_password_hash(password)

        assert check_password_hash("password123", salt, key) is False
        assert check_password_hash("PASSWORD123", salt, key) is False

    def test_check_password_hash_empty_password(self):
        """Test with empty password."""
        password = ""
        salt, key = generate_password_hash(password)

        assert check_password_hash("", salt, key) is True
        assert check_password_hash("not_empty", salt, key) is False

    def test_check_password_hash_unicode_password(self):
        """Test with unicode characters in password."""
        password = "pässwörd123"
        salt, key = generate_password_hash(password)

        assert check_password_hash(password, salt, key) is True
        assert check_password_hash("password123", salt, key) is False
