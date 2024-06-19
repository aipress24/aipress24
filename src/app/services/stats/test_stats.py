# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
from flask_sqlalchemy import SQLAlchemy

from ._models import StatsRecord


def test_create_record(db: SQLAlchemy) -> None:
    record = StatsRecord(
        date=arrow.now().date(),
        key="test",
        value=1,
    )
    db.session.add(record)
    db.session.flush()
