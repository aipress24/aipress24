# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.decorators import service

from app.models.admin import Promotion
from app.services.repositories import Repository


@service
class PromotionRepository(Repository[Promotion]):
    model_type = Promotion
