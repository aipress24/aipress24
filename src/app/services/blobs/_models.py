# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import IdMixin, Timestamped


class Blob(IdMixin, Timestamped, Base):
    __tablename__ = "blb_blob"
    """Model for storing large file content.

    Files are stored on a S3 storage, and possibly cached locally.

    A blob is immutable and timestamped.
    """

    uuid: Mapped[UUID] = mapped_column(unique=True, default=uuid4)
    s3_id: Mapped[str]
    sha256: Mapped[str]

    size: Mapped[int]
    filename: Mapped[str]
    mimetype: Mapped[str]

    @property
    def file(self) -> Path:
        """Path to a local copy of the blob."""
        return Path("TODO")

    @property
    def value(self) -> bytes:
        """Binary value content."""
        return self.file.read_bytes()

    @value.setter
    def value(self, value: bytes) -> None:
        """Store binary content to applications's repository and update
        `self.meta['md5']`.
        """
        self.file.write_bytes(value)
