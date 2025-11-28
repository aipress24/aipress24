# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from advanced_alchemy.repository import SQLAlchemySyncRepository
from flask_super.decorators import service

from app.services.repositories import Repository

from .communique import ComImage, Communique


#
# Commroom models
#
@service
class CommuniqueRepository(Repository[Communique]):
    model_type = Communique


class ComImageRepository(SQLAlchemySyncRepository[ComImage]):
    """Repository for ComImage model."""

    model_type = ComImage
