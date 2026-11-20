"""Base SQLAlchemy model configuration."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm


class Base(sa.orm.DeclarativeBase):
    pass
