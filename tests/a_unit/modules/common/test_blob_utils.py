# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for blob_utils module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from svcs.flask import container

from app.modules.common.blob_utils import add_blob_content, get_blob_content
from app.services.blobs import BlobService

if TYPE_CHECKING:
    from flask_sqlalchemy import SQLAlchemy


class TestAddBlobContent:
    """Test suite for add_blob_content function."""

    def test_add_blob_with_content(self, db: SQLAlchemy):
        """Test adding blob with valid content."""
        content = b"test content"

        blob_id = add_blob_content(content)

        assert blob_id != ""
        assert len(blob_id) == 32  # UUID hex is 32 characters

        # Verify blob was actually saved
        blob_service = container.get(BlobService)
        blob_path = blob_service.get_path(blob_id)
        assert blob_path.read_bytes() == content

    def test_add_blob_with_empty_bytes(self, db: SQLAlchemy):
        """Test adding blob with empty bytes returns empty string."""
        content = b""

        blob_id = add_blob_content(content)

        assert blob_id == ""

    def test_add_blob_with_large_content(self, db: SQLAlchemy):
        """Test adding blob with large content."""
        # 1MB of data
        content = b"x" * (1024 * 1024)

        blob_id = add_blob_content(content)

        assert blob_id != ""

        # Verify large content was saved correctly
        blob_service = container.get(BlobService)
        blob_path = blob_service.get_path(blob_id)
        assert blob_path.read_bytes() == content

    def test_add_blob_with_binary_content(self, db: SQLAlchemy):
        """Test adding blob with binary (non-text) content."""
        # Binary data with null bytes and various byte values
        content = bytes(range(256))

        blob_id = add_blob_content(content)

        assert blob_id != ""

        # Verify binary content preserved exactly
        blob_service = container.get(BlobService)
        blob_path = blob_service.get_path(blob_id)
        assert blob_path.read_bytes() == content

    def test_add_multiple_blobs_unique_ids(self, db: SQLAlchemy):
        """Test that multiple blobs get unique IDs."""
        content1 = b"first"
        content2 = b"second"

        blob_id1 = add_blob_content(content1)
        blob_id2 = add_blob_content(content2)

        assert blob_id1 != blob_id2
        assert blob_id1 != ""
        assert blob_id2 != ""

    def test_add_same_content_twice_different_ids(self, db: SQLAlchemy):
        """Test that adding same content twice creates different blobs."""
        content = b"duplicate"

        blob_id1 = add_blob_content(content)
        blob_id2 = add_blob_content(content)

        # Should create two separate blobs even with same content
        assert blob_id1 != blob_id2


class TestGetBlobContent:
    """Test suite for get_blob_content function."""

    def test_get_existing_blob(self, db: SQLAlchemy):
        """Test getting content of an existing blob."""
        content = b"test retrieval"

        # First save a blob
        blob_id = add_blob_content(content)

        # Then retrieve it
        retrieved_content = get_blob_content(blob_id)

        assert retrieved_content == content

    def test_get_blob_with_binary_content(self, db: SQLAlchemy):
        """Test getting binary content preserves all bytes."""
        content = bytes(range(256))

        blob_id = add_blob_content(content)
        retrieved_content = get_blob_content(blob_id)

        assert retrieved_content == content
        assert len(retrieved_content) == 256

    def test_get_nonexistent_blob(self, db: SQLAlchemy):
        """Test getting a non-existent blob returns empty bytes."""
        fake_blob_id = "00000000000000000000000000000000"

        content = get_blob_content(fake_blob_id)

        assert content == b""

    def test_get_blob_with_invalid_id(self, db: SQLAlchemy):
        """Test getting blob with invalid ID returns empty bytes."""
        invalid_id = "not-a-valid-id"

        content = get_blob_content(invalid_id)

        assert content == b""

    def test_get_empty_string_id(self, db: SQLAlchemy):
        """Test getting blob with empty string ID returns empty bytes."""
        content = get_blob_content("")

        assert content == b""

    def test_get_large_blob(self, db: SQLAlchemy):
        """Test getting large blob content."""
        # 1MB of data
        large_content = b"y" * (1024 * 1024)

        blob_id = add_blob_content(large_content)
        retrieved_content = get_blob_content(blob_id)

        assert retrieved_content == large_content
        assert len(retrieved_content) == 1024 * 1024


class TestBlobRoundTrip:
    """Integration tests for complete add/get cycles."""

    def test_round_trip_text_content(self, db: SQLAlchemy):
        """Test complete round trip with text-like content."""
        original = b"Hello, World!"

        blob_id = add_blob_content(original)
        retrieved = get_blob_content(blob_id)

        assert retrieved == original

    def test_round_trip_json_content(self, db: SQLAlchemy):
        """Test round trip with JSON-like content."""
        json_bytes = b'{"key": "value", "number": 123}'

        blob_id = add_blob_content(json_bytes)
        retrieved = get_blob_content(blob_id)

        assert retrieved == json_bytes

    def test_round_trip_utf8_content(self, db: SQLAlchemy):
        """Test round trip with UTF-8 encoded text."""
        utf8_text = "Hello 世界 🌍".encode()

        blob_id = add_blob_content(utf8_text)
        retrieved = get_blob_content(blob_id)

        assert retrieved == utf8_text
        # Verify it can be decoded back
        assert retrieved.decode("utf-8") == "Hello 世界 🌍"

    def test_multiple_round_trips(self, db: SQLAlchemy):
        """Test multiple independent round trips."""
        test_cases = [
            b"first",
            b"second with spaces",
            b"\x00\x01\x02",  # binary
            b"",  # empty (should return empty string for blob_id)
        ]

        for content in test_cases:
            blob_id = add_blob_content(content)
            if content:
                retrieved = get_blob_content(blob_id)
                assert retrieved == content
            else:
                # Empty content returns empty blob_id
                assert blob_id == ""

    def test_round_trip_preserves_exact_bytes(self, db: SQLAlchemy):
        """Test that no byte transformation occurs during save/load."""
        # Test with all possible byte values
        all_bytes = bytes(range(256))

        blob_id = add_blob_content(all_bytes)
        retrieved = get_blob_content(blob_id)

        # Verify every single byte matches
        assert len(retrieved) == 256
        for i in range(256):
            assert retrieved[i] == i
