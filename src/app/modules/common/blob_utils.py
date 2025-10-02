"""Utilities for BlobService access."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from svcs.flask import container

from app.services.blobs import BlobService


def add_blob_content(content: bytes) -> str:
    """Save the bytes content as a Blob and return its id."""
    if not content:
        return ""
    # length must already be checked by UI
    blob_service = container.get(BlobService)
    blob = blob_service.save(content)
    return blob.id


def get_blob_content(blob_id: str) -> bytes:
    """Return the Blob bytes content from it's id."""
    blob_service = container.get(BlobService)
    try:
        blob_path = blob_service.get_path(blob_id)
        return blob_path.read_bytes()
    except Exception:
        return b""
