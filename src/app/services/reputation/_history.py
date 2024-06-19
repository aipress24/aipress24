# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random
from datetime import date

import arrow
from rich import progress
from sqlalchemy import select
from sqlalchemy.engine.result import ScalarResult

from app.flask.extensions import db
from app.models.auth import User

from ._compute import compute_reputation
from ._models import ReputationRecord


def update_reputations(show_progress: bool = False, add_noise: bool = False) -> None:
    today = arrow.now().date()
    users = list(_get_all_users())
    if show_progress:
        tracker = progress.track(users, description="Updating reputations")
    else:
        tracker = users
    for user in tracker:
        _update_for_user(user, today, add_noise=add_noise)
        db.session.commit()


def get_reputation_history(user: User) -> list[ReputationRecord]:
    R = ReputationRecord  # noqa: N806
    stmt = select(R).where(R.user_id == user.id).order_by(R.date)
    return list(db.session.scalars(stmt))


#
# Internal
#
def _get_all_users() -> ScalarResult:
    # FIXME: only active users
    stmt = select(User)
    return db.session.scalars(stmt)


def _update_for_user(user: User, today: date, add_noise: bool = False) -> None:
    reputation_details = compute_reputation(user)

    # TODO: apply decay
    karma = reputation_details["total"]
    if add_noise:
        karma += _noise()

    # Delete today's value if it exists
    R = ReputationRecord  # noqa: N806
    stmt = select(R).where(R.user_id == user.id, R.date == today)
    record = db.session.scalar(stmt)

    if not record:
        record = ReputationRecord(user_id=user.id, date=today)
        db.session.add(record)

    user.karma = record.value = karma
    record.details = reputation_details


def _noise() -> float:
    # TEMP: add some noise to avoid having a constant reputation
    return random.uniform(-0.1, 0.1)
