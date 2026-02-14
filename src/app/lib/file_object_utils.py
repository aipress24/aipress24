# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Utilities for FileObject creation and serialization.

This module provides helpers for working with Advanced Alchemy's FileObject,
including content-addressable storage using SHA256 hashes to avoid filename
collisions.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from advanced_alchemy.types import FileObject


def create_file_object(
    content: bytes,
    original_filename: str,
    backend: str = "s3",
    content_type: str | None = None,
) -> FileObject:
    """Create a FileObject with content-hash-based storage path.

    Uses SHA256 hash of content as the storage filename to avoid collisions
    when multiple users upload files with the same name.

    Args:
        content: The file content as bytes.
        original_filename: Original filename (kept for display, used for extension).
        backend: Storage backend name (default: "s3").
        content_type: Optional MIME type.

    Returns:
        FileObject ready to be saved and assigned to a model field.

    Example:
        >>> file_obj = create_file_object(
        ...     content=uploaded_file.read(),
        ...     original_filename="photo.jpg",
        ...     content_type="image/jpeg",
        ... )
        >>> user.photo_image = file_obj
    """
    content_hash = hashlib.sha256(content).hexdigest()
    ext = Path(original_filename).suffix.lower()  # .jpg, .png, etc.
    storage_name = f"{content_hash}{ext}"

    return FileObject(
        backend=backend,
        filename=original_filename,  # Keep original for display
        to_filename=storage_name,  # Hash-based storage path
        content=content,
        content_type=content_type,
    )


def deserialize_file_object(file_data: dict[str, Any] | None) -> FileObject | None:
    """Deserialize a FileObject from a dictionary.

    Args:
        file_data: Dictionary containing FileObject attributes.

    Returns:
        FileObject instance or None if data is invalid.
    """
    if (
        isinstance(file_data, dict)
        and file_data.get("backend")
        and file_data.get("filename")
    ):
        try:
            return FileObject(
                backend=file_data["backend"],
                filename=file_data["filename"],
                to_filename=file_data.get("to_filename"),
                content_type=file_data.get("content_type"),
                size=file_data.get("size"),
                last_modified=file_data.get("last_modified"),
                checksum=file_data.get("checksum"),
                etag=file_data.get("etag"),
                version_id=file_data.get("version_id"),
                metadata=file_data.get("metadata"),
            )
        except (KeyError, ValueError, TypeError):
            return None
    return None
