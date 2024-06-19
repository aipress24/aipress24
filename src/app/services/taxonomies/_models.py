# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Simple model for taxonomies.
"""

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import IdMixin


class TaxonomyEntry(IdMixin, Base):
    __tablename__ = "tax_taxonomy"

    #: the name of this entity (i.e. entry)
    name: Mapped[str] = mapped_column(index=True)

    #: the name of the taxonomy it belongs to ("subject", "sector", etc.)
    taxonomy_name: Mapped[str]
