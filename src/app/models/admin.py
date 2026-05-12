"""Admin models for promotional content management."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import ProfileEnum
from app.models.base import Base


class Promotion(Base):
    """Model for promotional content with title and body text."""

    __tablename__ = "adm_promotion"

    slug: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(default="")
    body: Mapped[str] = mapped_column(default="")
    # Explicit ``name=`` is load-bearing: without it SQLAlchemy derives
    # the PG type name from the Python class (``profileenum``), but the
    # existing schema has the type as ``adm_profileenum``. Dropping the
    # argument silently triggers an enum-rename migration that requires
    # ownership of the type — privileges the app user doesn't have in
    # prod.
    profile: Mapped[ProfileEnum] = mapped_column(
        sa.Enum(ProfileEnum, name="adm_profileenum"), nullable=True
    )
