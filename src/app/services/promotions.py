# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa

from app.flask.extensions import db
from app.models.admin import Promotion


def get_promotion(slug: str) -> Promotion:
    stmt = sa.select(Promotion).where(Promotion.slug == slug)
    box = db.session.execute(stmt).scalar_one_or_none()
    assert box
    return box
