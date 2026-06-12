# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for `app.services.reputation._history`.

`update_reputations` is the hourly cron entry that walks every user
and refreshes their `ReputationRecord` (the per-day audit row that
feeds the visibility / karma surfaces). The original a_unit tests
were skipped for formula drift and the only DB-level coverage was
the implicit one through `compute_reputation`. This file pins the
upsert + history behaviour at b_integration.

Pattern : seed users via `db_session`, call the real entry point,
inspect the resulting `ReputationRecord` rows. Because
`update_reputations()` commits per user (cron-friendly, no batch
rollback), we purge any rows we created in a teardown step so
nothing leaks across tests.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import TYPE_CHECKING

import arrow
import pytest
from sqlalchemy import select

from app.models.auth import User
from app.services.reputation._history import (
    _noise,
    _update_for_user,
    get_reputation_history,
    update_reputations,
)
from app.services.reputation._models import ReputationRecord

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _fresh_user(db_session: Session, *, label: str = "u") -> User:
    """Minimum-viable user. Email uniqueness is enforced ; mint a
    fresh slug per call so several users co-exist in one test."""
    u = User(
        email=f"rep-{label}-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Rep",
        last_name="Tester",
        active=True,
    )
    db_session.add(u)
    db_session.flush()
    return u


_TEST_EMAIL_PREFIX = "rep-"


@pytest.fixture(autouse=True)
def _purge_test_artifacts(db_session: Session):
    """`update_reputations` commits per user (mirrors cron semantics),
    so the surrounding savepoint can't roll back any of the rows our
    tests created. Sweep them in teardown :

    * Every `ReputationRecord` whose owning user's email starts with
      our test prefix.
    * Every `User` whose email starts with our test prefix.

    The prefix scoping leaves any unrelated row alone — a parallel
    test that genuinely needs `update_reputations` behaviour on
    non-test users (none today) would be unaffected.
    """
    yield
    test_users = (
        db_session.execute(
            select(User).where(User.email.like(f"{_TEST_EMAIL_PREFIX}%"))
        )
        .scalars()
        .all()
    )
    if not test_users:
        return

    user_ids = {u.id for u in test_users}
    test_records = (
        db_session.execute(
            select(ReputationRecord).where(ReputationRecord.user_id.in_(user_ids))
        )
        .scalars()
        .all()
    )
    for record in test_records:
        db_session.delete(record)
    for u in test_users:
        db_session.delete(u)
    db_session.commit()


# ---------------------------------------------------------------------------
# _noise — random spread bound
# ---------------------------------------------------------------------------


class TestNoise:
    def test_returns_float_in_documented_range(self) -> None:
        """The cron actor's add_noise=True path calls this — the
        spread must stay tight enough that real signal isn't drowned
        out. ±0.1 is the documented bound."""
        for _ in range(100):
            value = _noise()
            assert -0.1 <= value <= 0.1
            assert isinstance(value, float)


# ---------------------------------------------------------------------------
# _update_for_user — single-row upsert behaviour
# ---------------------------------------------------------------------------


class TestUpdateForUser:
    def test_creates_record_for_first_call(self, db_session: Session) -> None:
        user = _fresh_user(db_session, label="create")
        today = arrow.now().date()

        _update_for_user(user, today)
        db_session.flush()

        stmt = (
            select(ReputationRecord)
            .where(ReputationRecord.user_id == user.id)
            .where(ReputationRecord.date == today)
        )
        record = db_session.execute(stmt).scalar_one_or_none()
        assert record is not None

    def test_idempotent_on_same_day(self, db_session: Session) -> None:
        """The composite PK is (user_id, date) — a second call on the
        same date must UPDATE the existing row, not create a duplicate."""
        user = _fresh_user(db_session, label="idemp")
        today = arrow.now().date()

        _update_for_user(user, today)
        _update_for_user(user, today)
        db_session.flush()

        count = db_session.execute(
            select(ReputationRecord)
            .where(ReputationRecord.user_id == user.id)
            .where(ReputationRecord.date == today)
        ).all()
        assert len(count) == 1

    def test_writes_zero_karma_for_fresh_user(self, db_session: Session) -> None:
        """A user with no follows / articles has compute_reputation == 0.
        Pin so a refactor that loses the « total » key (or returns
        None) doesn't silently write None to the value column."""
        user = _fresh_user(db_session, label="zero")
        today = arrow.now().date()

        _update_for_user(user, today)
        db_session.flush()

        record = db_session.execute(
            select(ReputationRecord)
            .where(ReputationRecord.user_id == user.id)
            .where(ReputationRecord.date == today)
        ).scalar_one()
        assert record.value == 0

    def test_mirrors_value_onto_user_karma(self, db_session: Session) -> None:
        """`user.karma = record.value = karma` — both columns are kept
        in sync. The user-side denormalisation lets the dashboard show
        karma without a JOIN ; pin so a refactor that drops the
        denorm doesn't silently break the display."""
        user = _fresh_user(db_session, label="karma-mirror")
        today = arrow.now().date()

        _update_for_user(user, today)
        db_session.flush()

        record = db_session.execute(
            select(ReputationRecord).where(ReputationRecord.user_id == user.id)
        ).scalar_one()
        assert user.karma == record.value

    def test_stores_full_reputation_details_dict(self, db_session: Session) -> None:
        """The `details` JSON column carries the full breakdown
        compute_reputation returned — used by the history endpoint
        to render per-source contribution. Pin so a refactor that
        only stores `{"total": ...}` doesn't strip the breakdown."""
        user = _fresh_user(db_session, label="details")
        today = arrow.now().date()

        _update_for_user(user, today)
        db_session.flush()

        record = db_session.execute(
            select(ReputationRecord).where(ReputationRecord.user_id == user.id)
        ).scalar_one()
        assert isinstance(record.details, dict)
        # `total` is always present in compute_reputation's return shape.
        assert "total" in record.details

    def test_add_noise_perturbs_karma_within_bound(self, db_session: Session) -> None:
        """When the cron actor passes add_noise=True, the stored
        karma deviates from compute_reputation's raw total by
        at most ±0.1 (the _noise spread)."""
        user = _fresh_user(db_session, label="noisy")
        today = arrow.now().date()

        _update_for_user(user, today, add_noise=True)
        db_session.flush()

        record = db_session.execute(
            select(ReputationRecord).where(ReputationRecord.user_id == user.id)
        ).scalar_one()
        # Raw fresh-user reputation is 0 ; noise puts us in [-0.1, 0.1].
        assert -0.1 <= record.value <= 0.1
        # And the user-side denormalised karma matches the record.
        assert user.karma == record.value

    def test_distinct_dates_yield_distinct_records(self, db_session: Session) -> None:
        """The composite PK lets one user have many records (one per
        day). Pin so a refactor that switches to a single-row
        latest-only schema is conscious."""
        user = _fresh_user(db_session, label="multi-day")
        today = arrow.now().date()
        yesterday = today - timedelta(days=1)

        _update_for_user(user, today)
        _update_for_user(user, yesterday)
        db_session.flush()

        records = (
            db_session.execute(
                select(ReputationRecord).where(ReputationRecord.user_id == user.id)
            )
            .scalars()
            .all()
        )
        dates = sorted(r.date for r in records)
        assert dates == [yesterday, today]


# ---------------------------------------------------------------------------
# update_reputations — the cron orchestrator
# ---------------------------------------------------------------------------


class TestUpdateReputations:
    def test_writes_a_record_for_a_fresh_user(self, db_session: Session) -> None:
        """The hourly cron must produce a record for every user
        present at run time. Pin the happy path."""
        user = _fresh_user(db_session, label="cron-fresh")
        db_session.commit()  # flush the user past the savepoint

        update_reputations()

        history = get_reputation_history(user)
        assert len(history) == 1
        assert history[0].user_id == user.id

    def test_idempotent_re_run_on_same_day(self, db_session: Session) -> None:
        """The actor schedule fires hourly ; re-running on the same
        day must update, not duplicate."""
        user = _fresh_user(db_session, label="cron-idemp")
        db_session.commit()

        update_reputations()
        update_reputations()

        history = get_reputation_history(user)
        assert len(history) == 1

    def test_processes_multiple_users_independently(self, db_session: Session) -> None:
        """The loop must not abort on per-user failures (it commits
        per user). For two fresh users, both should get records."""
        alice = _fresh_user(db_session, label="alice")
        bob = _fresh_user(db_session, label="bob")
        db_session.commit()

        update_reputations()

        assert len(get_reputation_history(alice)) == 1
        assert len(get_reputation_history(bob)) == 1

    def test_add_noise_propagates_to_record(self, db_session: Session) -> None:
        """The actor's optional add_noise=True flag flows all the way
        into the stored record. Pin so the actor → service kwarg path
        doesn't silently drop."""
        user = _fresh_user(db_session, label="cron-noisy")
        db_session.commit()

        update_reputations(add_noise=True)

        history = get_reputation_history(user)
        assert len(history) == 1
        # Fresh user → base 0 ; noisy → within ±0.1.
        assert -0.1 <= history[0].value <= 0.1


# ---------------------------------------------------------------------------
# get_reputation_history — read path
# ---------------------------------------------------------------------------


class TestGetReputationHistory:
    def test_empty_for_user_with_no_records(self, db_session: Session) -> None:
        user = _fresh_user(db_session, label="empty")
        assert get_reputation_history(user) == []

    def test_returns_records_sorted_by_date(self, db_session: Session) -> None:
        """The history endpoint renders a timeseries — the ordering
        contract is « ascending by date ». Pin so a refactor that
        flips desc doesn't silently invert the chart."""
        user = _fresh_user(db_session, label="ordered")
        days_back = [10, 5, 1]  # intentionally out of order

        for d in days_back:
            stamp = date.today() - timedelta(days=d)  # noqa: DTZ011
            _update_for_user(user, stamp)
        db_session.flush()

        history = get_reputation_history(user)
        assert [r.date for r in history] == sorted(r.date for r in history)

    def test_only_returns_records_for_the_queried_user(
        self, db_session: Session
    ) -> None:
        alice = _fresh_user(db_session, label="alice-isolated")
        bob = _fresh_user(db_session, label="bob-isolated")
        today = arrow.now().date()
        _update_for_user(alice, today)
        _update_for_user(bob, today)
        db_session.flush()

        alice_history = get_reputation_history(alice)
        assert all(r.user_id == alice.id for r in alice_history)
        assert len(alice_history) == 1
