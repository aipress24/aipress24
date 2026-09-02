# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""DB round-trip integration tests for ``events/services.py``.

Why this lives at the ``b_integration`` tier
--------------------------------------------
The pure predicates (``_is_user_in``, ``can_user_accredit``) are already
covered by ``tests/a_unit/modules/events/test_event_services_pure.py`` with
hand-rolled stand-ins and no DB.

This file covers the *imperative shell* — the four functions that actually
hit the ``evt_participation`` association table:

* ``is_participant`` — reflects the current state of the table.
* ``get_participants`` — loads ``User`` rows back from the table, honours
  ``order_by`` and ``limit``.

These behaviours are only meaningfully testable against a real SQLAlchemy
session: the SUT issues raw ``sa.insert`` / ``sa.delete`` / ``sa.select``
statements through ``db.session``. Mocking the session would test only the
mock, not the SQL. So we drive the real engine via the autouse
``db_session`` fixture (savepoint rollback after every test) and assert on
tangible row state.

Only ``EventPost`` rows can participate — the association table FKs
``event_id`` to ``evt_event_post.id``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa

from app.models.auth import User
from app.modules.events.models import (
    Accreditation,
    AccreditationStatus,
    EventPost,
)
from app.modules.events.services import (
    get_participants,
    is_participant,
    withdraw_accreditation,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ----------------------------------------------------------------
# Fixtures — real model rows, no mocks
# ----------------------------------------------------------------


def _accredit(db_session, event, user) -> None:
    """Make `user` accredited, by writing the row.

    `add_participant` did this until lot L2 removed it; the tests below
    only ever used it as setup.
    """
    db_session.add(
        Accreditation(
            event_id=event.id, user_id=user.id, status=AccreditationStatus.ACCEPTED
        )
    )
    db_session.flush()


@pytest.fixture
def users(db_session: Session) -> list[User]:
    """Three real ``User`` rows, flushed so ``id`` is populated."""
    rows = []
    for i in range(3):
        u = User(email=f"rt-user{i}@example.com")
        u.photo = b""
        u.active = True
        db_session.add(u)
        rows.append(u)
    db_session.flush()
    return rows


@pytest.fixture
def event(db_session: Session, users: list[User]) -> EventPost:
    """A real ``EventPost`` row. Used for the ``isinstance(EventPost)`` path."""
    e = EventPost(title="Round Trip Event", content="...", owner=users[0])
    db_session.add(e)
    db_session.flush()
    return e


def _participation_row_count(db_session: Session, event_id: int) -> int:
    """Count accredited members for a given event (state probe)."""
    stmt = sa.select(sa.func.count()).where(
        Accreditation.event_id == event_id,
        Accreditation.status == AccreditationStatus.ACCEPTED,
    )
    return db_session.execute(stmt).scalar() or 0


# ----------------------------------------------------------------
# ----------------------------------------------------------------


# NOTE: an earlier `test_works_for_concrete_subclasses` was deleted.
# Its premise was wrong: the five event subtypes were siblings of
# `EventPost`, not subclasses — they wrote to their own tables and
# never landed in `evt_event_post`, which is what
# `Accreditation.event_id` FKs to. SQLite skipped the FK check ;
# Postgres surfaced the violation. Those classes are gone since lot
# C0b ; only `EventPost` remains.


# ----------------------------------------------------------------
# ----------------------------------------------------------------


# ----------------------------------------------------------------
# is_participant
# ----------------------------------------------------------------


class TestIsParticipantRoundTrip:
    """``is_participant`` must reflect the association-table state."""

    def test_false_when_no_row(
        self, db_session: Session, event: EventPost, users: list[User]
    ) -> None:
        assert is_participant(event, users[0]) is False

    def test_true_after_add(
        self, db_session: Session, event: EventPost, users: list[User]
    ) -> None:
        _accredit(db_session, event, users[0])

        assert is_participant(event, users[0]) is True

    def test_false_after_remove(
        self, db_session: Session, event: EventPost, users: list[User]
    ) -> None:
        _accredit(db_session, event, users[0])
        withdraw_accreditation(event, users[0])

        assert is_participant(event, users[0]) is False

    def test_isolation_between_events(
        self, db_session: Session, users: list[User]
    ) -> None:
        e1 = EventPost(title="E1", owner=users[0])
        e2 = EventPost(title="E2", owner=users[0])
        db_session.add_all([e1, e2])
        db_session.flush()

        _accredit(db_session, e1, users[0])

        assert is_participant(e1, users[0]) is True
        assert is_participant(e2, users[0]) is False


# ----------------------------------------------------------------
# get_participants
# ----------------------------------------------------------------


class TestGetParticipantsRoundTrip:
    """``get_participants`` must round-trip through the DB and honour
    ``order_by`` / ``limit``."""

    def test_empty_event_returns_empty_list(
        self, db_session: Session, event: EventPost
    ) -> None:
        assert get_participants(event) == []

    def test_returns_added_users(
        self, db_session: Session, event: EventPost, users: list[User]
    ) -> None:
        _accredit(db_session, event, users[0])
        _accredit(db_session, event, users[2])
        db_session.flush()

        result = get_participants(event)

        assert {u.id for u in result} == {users[0].id, users[2].id}
        assert all(isinstance(u, User) for u in result)

    def test_order_by_email_asc(
        self, db_session: Session, event: EventPost, users: list[User]
    ) -> None:
        # Insert in non-sorted order to make the ordering observable.
        for idx in (2, 0, 1):
            _accredit(db_session, event, users[idx])
        db_session.flush()

        result = get_participants(event, order_by=User.email.asc())

        emails = [u.email for u in result]
        assert emails == sorted(emails)

    def test_limit_truncates_result(
        self, db_session: Session, event: EventPost, users: list[User]
    ) -> None:
        for u in users:
            _accredit(db_session, event, u)
        db_session.flush()

        result = get_participants(event, limit=2)

        assert len(result) == 2

    def test_rejects_non_event_post(self, db_session: Session) -> None:
        # Guard the ``isinstance(event, EventPost)`` check at the top of
        # ``get_participants`` — passing something else must raise.
        with pytest.raises(TypeError, match="Expected EventPost"):
            get_participants("not an event")  # type: ignore[arg-type]
