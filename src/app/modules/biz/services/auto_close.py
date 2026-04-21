# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Marketplace — auto-close of expired offers.

Driven by the `flask biz close-expired` CLI. Iterates over every OPEN
offer (mission / project / job) and flips it to CLOSED if its deadline
(`deadline` for missions and projects, `starting_date` for jobs) is
past. Returns per-kind counts for reporting.
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa

from app.flask.extensions import db
from app.modules.biz.models import (
    JobOffer,
    MissionOffer,
    MissionStatus,
    ProjectOffer,
)


def close_expired_offers() -> dict[str, int]:
    """Flip every expired OPEN offer to CLOSED. Returns per-kind counts."""
    now = datetime.now(UTC)

    counts = {
        "missions": _close_for(MissionOffer, MissionOffer.deadline, now),
        "projects": _close_for(ProjectOffer, ProjectOffer.deadline, now),
        "jobs": _close_for(JobOffer, JobOffer.starting_date, now),
    }
    db.session.commit()
    return counts


def _close_for(model, date_col, now: datetime) -> int:
    """Close every OPEN row where `date_col < now`. Return count closed."""
    result = db.session.execute(
        sa.update(model)
        .where(model.mission_status == MissionStatus.OPEN)
        .where(date_col.is_not(None))
        .where(date_col < now)
        .values(mission_status=MissionStatus.CLOSED)
    )
    return result.rowcount or 0
