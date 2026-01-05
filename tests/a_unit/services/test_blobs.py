# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from flask_sqlalchemy import SQLAlchemy
from svcs.flask import container
from typeguard import TypeCheckError
from werkzeug.datastructures import FileStorage

from app.services.blobs import BlobService


def test_blob_lifecycle(db: SQLAlchemy) -> None:
    blob_service = container.get(BlobService)

    blob = blob_service.save(b"foo")
    path = blob_service.get_path(blob.id)
    assert path.read_bytes() == b"foo"


def test_save_bytes(db: SQLAlchemy) -> None:
    """Test saving bytes directly."""
    blob_service = container.get(BlobService)

    blob = blob_service.save(b"test content")

    assert blob.id is not None
    assert blob.size == 12  # len(b"test content")
    assert blob.path.read_bytes() == b"test content"


def test_save_bytesio(db: SQLAlchemy) -> None:
    """Test saving BytesIO object."""
    blob_service = container.get(BlobService)

    data = BytesIO(b"bytesio content")
    blob = blob_service.save(data)

    assert blob.id is not None
    assert blob.size == 15  # len(b"bytesio content")
    assert blob.path.read_bytes() == b"bytesio content"


def test_save_file_storage(db: SQLAlchemy) -> None:
    """Test saving FileStorage object."""
    blob_service = container.get(BlobService)

    file_data = BytesIO(b"file storage content")
    file_storage = FileStorage(stream=file_data, filename="test.txt")
    blob = blob_service.save(file_storage)

    assert blob.id is not None
    assert blob.size == 20  # len(b"file storage content")
    assert blob.path.read_bytes() == b"file storage content"


def test_save_unsupported_type(db: SQLAlchemy) -> None:
    """Test saving with unsupported type raises ValueError or TypeCheckError."""
    blob_service = container.get(BlobService)

    # With typeguard, TypeCheckError is raised at function boundary
    # Without typeguard, ValueError is raised when handling the unsupported type
    with pytest.raises((ValueError, TypeCheckError)):
        blob_service.save(123)  # type: ignore[arg-type]

    with pytest.raises((ValueError, TypeCheckError)):
        blob_service.save("string")  # type: ignore[arg-type]


def test_get_blob(db: SQLAlchemy) -> None:
    """Test getting a blob by ID."""
    blob_service = container.get(BlobService)

    # Save a blob first
    saved_blob = blob_service.save(b"get test")

    # Get it back
    retrieved_blob = blob_service.get(saved_blob.id)

    assert retrieved_blob.id == saved_blob.id
    assert retrieved_blob.size == saved_blob.size
    assert retrieved_blob.path == saved_blob.path


def test_get_path(db: SQLAlchemy) -> None:
    """Test get_path method."""
    blob_service = container.get(BlobService)

    blob = blob_service.save(b"path test")
    path = blob_service.get_path(blob.id)

    assert isinstance(path, Path)
    assert path.exists()
    assert path.read_bytes() == b"path test"
