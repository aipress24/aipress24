# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from advanced_alchemy.repository import SQLAlchemySyncRepository
from advanced_alchemy.repository.typing import ModelT
from sqlalchemy.orm import scoped_session
from svcs.flask import container


class Repository(SQLAlchemySyncRepository[ModelT]):
    """Base class for repositories."""

    @classmethod
    def svcs_factory(cls):
        session = container.get(scoped_session)
        return cls(session=session)
