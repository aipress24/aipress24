"""Temporary blob storage model for KYC document processing."""

# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
#
from __future__ import annotations

from sqlalchemy import LargeBinary
from sqlalchemy.orm import Mapped, mapped_column

# from ..database import Base
from .base import Base


class KYCTmpBlob(Base):
    """Temporary blob storage for KYC (Know Your Customer) documents."""

    __tablename__ = "kyc_tmp_blob"

    id: Mapped[int] = mapped_column(primary_key=True, unique=True, autoincrement=True)
    name: Mapped[str]
    uuid: Mapped[str]
    content: Mapped[bytes] = mapped_column(LargeBinary)
