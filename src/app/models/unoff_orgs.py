# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unofficial organisation

Basically, a name of organisation declared by a user.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import LifeCycleMixin


class UnoffOrganisation(LifeCycleMixin, Base):
    """
    -Nom: String[I] unique
    """

    __tablename__ = "unoff_organisation"

    name: Mapped[str] = mapped_column(sa.String, unique=True, primary_key=True)
