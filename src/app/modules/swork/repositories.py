# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.decorators import service

from app.models.short_post import ShortPost
from app.services.repositories import OwnedRepository


@service
class ShortPostRepository(OwnedRepository[ShortPost]):
    model_type = ShortPost
