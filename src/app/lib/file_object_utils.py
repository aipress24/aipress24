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

_PLACEHOLDER_IMAGE_URL = "/static/img/gray-texture.png"


def media_url(file_object: FileObject | None) -> str:
    """Return the /media URL for a content-addressed FileObject.

    Uses the hash-based storage key so the URL is stable, cache-friendly,
    and independent of the parent row. FileObject.path returns the
    to_filename (the sha256-based storage name set by create_file_object)
    when present, else the original filename. Legacy non-hashed names get
    rejected by the /media endpoint's regex and fall through to a broken-
    image icon — same visible result as the placeholder fallback used for
    missing content.
    """
    if file_object and file_object.path:
        return f"/media/{file_object.path}"
    return _PLACEHOLDER_IMAGE_URL


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
        ...     content=b"fake image content",
        ...     original_filename="photo.jpg",
        ...     content_type="image/jpeg",
        ... )
        >>> # user.photo_image = file_obj
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
