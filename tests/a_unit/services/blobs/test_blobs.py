# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from svcs.flask import container

from app.services.blobs import BlobService


def test_blob_lifecycle(db: SQLAlchemy) -> None:
    blob_service = container.get(BlobService)

    blob = blob_service.save(b"foo")
    path = blob_service.get_path(blob.id)
    assert path.read_bytes() == b"foo"
