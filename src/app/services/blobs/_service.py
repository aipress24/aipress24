# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Simple blob service.

TODO:
- Make it more robust
- Store metadata in database
- Store data in S3 or support multiple storage backends
- Use a cache for the files
"""

from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path

from attr import define, frozen
from flask import current_app
from flask_super.decorators import service
from sqlalchemy.orm import scoped_session
from svcs import Container
from werkzeug.datastructures import FileStorage


@define
class Blob:
    id: str
    name: str
    size: int
    mime_type: str

    @property
    def path(self) -> Path:
        return _get_blobs_dir() / self.id


@service
@frozen
class BlobService:
    db_session: scoped_session

    @classmethod
    def svcs_factory(cls, ctn: Container) -> BlobService:
        return cls(db_session=ctn.get(scoped_session))

    def get(self, blob_id: str) -> Blob:
        file = _get_blobs_dir() / blob_id
        size = file.stat().st_size
        blob = Blob(id=blob_id, name="", size=size, mime_type="")
        return blob

    def get_path(self, blob_id: str) -> Path:
        blob = self.get(blob_id)
        return blob.path

    def save(self, file_or_path_or_data: bytes | BytesIO | Path | FileStorage) -> Blob:
        blob_id = uuid.uuid4().hex
        blob_path = _get_blobs_dir() / blob_id

        match file_or_path_or_data:
            case bytes():
                blob_path.write_bytes(file_or_path_or_data)
            case BytesIO() | FileStorage():
                blob_path.write_bytes(file_or_path_or_data.read())
            case Path():
                blob_path.write_bytes(file_or_path_or_data.read_bytes())
            case _:
                msg = f"Unsupported type {type(file_or_path_or_data)}"
                raise ValueError(msg)

        blob = Blob(id=blob_id, name="", size=blob_path.stat().st_size, mime_type="")
        return blob


def _get_blobs_dir() -> Path:
    blobs_dir = Path(current_app.instance_path) / "blobs"
    blobs_dir.mkdir(exist_ok=True, parents=True)
    return blobs_dir
