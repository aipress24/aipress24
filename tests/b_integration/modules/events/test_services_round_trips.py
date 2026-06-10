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

* ``add_participant`` — inserts a row, is idempotent on re-adds.
* ``remove_participant`` — deletes a row, is idempotent on missing rows.
* ``is_participant`` — reflects the current state of the table.
* ``get_participants`` — loads ``User`` rows back from the table, honours
  ``order_by`` and ``limit``.

These behaviours are only meaningfully testable against a real SQLAlchemy
session: the SUT issues raw ``sa.insert`` / ``sa.delete`` / ``sa.select``
statements through ``db.session``. Mocking the session would test only the
mock, not the SQL. So we drive the real engine via the autouse
``db_session`` fixture (savepoint rollback after every test) and assert on
tangible row state.

Only true ``EventPost`` rows can participate — the association table
FKs ``event_id`` to ``evt_event_post.id``, and the sibling classes
``PublicEvent`` / ``PressEvent`` write to their own tables and never
land in ``evt_event_post``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa

from app.models.auth import User
from app.modules.events.models import (
    EventPost,
    participation_table,
)
from app.modules.events.services import (
    add_participant,
    get_participants,
    is_participant,
    remove_participant,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ----------------------------------------------------------------
# Fixtures — real model rows, no mocks
# ----------------------------------------------------------------


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
    """Count rows in the association table for a given event (state probe)."""
    stmt = sa.select(sa.func.count()).where(
        participation_table.c.event_id == event_id,
    )
    return db_session.execute(stmt).scalar() or 0


# ----------------------------------------------------------------
# add_participant
# ----------------------------------------------------------------


class TestAddParticipantRoundTrip:
    """``add_participant`` must insert a row and be idempotent."""

    def test_insert_creates_row(
        self, db_session: Session, event: EventPost, users: list[User]
    ) -> None:
        assert _participation_row_count(db_session, event.id) == 0

        inserted = add_participant(event, users[0])
        db_session.flush()

        assert inserted is True
        assert _participation_row_count(db_session, event.id) == 1

    def test_insert_is_idempotent(
        self, db_session: Session, event: EventPost, users: list[User]
    ) -> None:
        add_participant(event, users[0])
        db_session.flush()

        second = add_participant(event, users[0])
        db_session.flush()

        assert second is False
        assert _participation_row_count(db_session, event.id) == 1

    def test_multiple_users_can_join(
        self, db_session: Session, event: EventPost, users: list[User]
    ) -> None:
        for u in users:
            assert add_participant(event, u) is True
        db_session.flush()

        assert _participation_row_count(db_session, event.id) == len(users)

    # NOTE: an earlier `test_works_for_concrete_subclasses[PublicEvent | PressEvent]`
    # was deleted. Its premise was wrong: `PublicEvent` and `PressEvent` are
    # siblings of `EventPost`, not subclasses — they write to their own tables
    # (`evt_public_event` / `evt_press_event`) and never land in `evt_event_post`.
    # `participation_table.event_id` FKs to `EventPost.id`, so the SUT only
    # supports true `EventPost` instances. SQLite skipped the FK check ; Postgres
    # surfaced the violation. The behaviour is correct ; the test was buggy.


# ----------------------------------------------------------------
# remove_participant
# ----------------------------------------------------------------


class TestRemoveParticipantRoundTrip:
    """``remove_participant`` must delete the row and be idempotent."""

    def test_add_then_remove_clears_row(
        self, db_session: Session, event: EventPost, users: list[User]
    ) -> None:
        add_participant(event, users[0])
        db_session.flush()
        assert _participation_row_count(db_session, event.id) == 1

        removed = remove_participant(event, users[0])
        db_session.flush()

        assert removed is True
        assert _participation_row_count(db_session, event.id) == 0

    def test_remove_when_absent_is_idempotent(
        self, db_session: Session, event: EventPost, users: list[User]
    ) -> None:
        # No prior add → the row isn't there.
        removed = remove_participant(event, users[0])
        db_session.flush()

        assert removed is False
        assert _participation_row_count(db_session, event.id) == 0

    def test_remove_only_target_user(
        self, db_session: Session, event: EventPost, users: list[User]
    ) -> None:
        for u in users:
            add_participant(event, u)
        db_session.flush()
        assert _participation_row_count(db_session, event.id) == 3

        remove_participant(event, users[1])
        db_session.flush()

        assert _participation_row_count(db_session, event.id) == 2
        # The other two are still there.
        assert is_participant(event, users[0]) is True
        assert is_participant(event, users[1]) is False
        assert is_participant(event, users[2]) is True


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
        add_participant(event, users[0])
        db_session.flush()

        assert is_participant(event, users[0]) is True

    def test_false_after_remove(
        self, db_session: Session, event: EventPost, users: list[User]
    ) -> None:
        add_participant(event, users[0])
        db_session.flush()
        remove_participant(event, users[0])
        db_session.flush()

        assert is_participant(event, users[0]) is False

    def test_isolation_between_events(
        self, db_session: Session, users: list[User]
    ) -> None:
        e1 = EventPost(title="E1", owner=users[0])
        e2 = EventPost(title="E2", owner=users[0])
        db_session.add_all([e1, e2])
        db_session.flush()

        add_participant(e1, users[0])
        db_session.flush()

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
        add_participant(event, users[0])
        add_participant(event, users[2])
        db_session.flush()

        result = get_participants(event)

        assert {u.id for u in result} == {users[0].id, users[2].id}
        assert all(isinstance(u, User) for u in result)

    def test_order_by_email_asc(
        self, db_session: Session, event: EventPost, users: list[User]
    ) -> None:
        # Insert in non-sorted order to make the ordering observable.
        for idx in (2, 0, 1):
            add_participant(event, users[idx])
        db_session.flush()

        result = get_participants(event, order_by=User.email.asc())

        emails = [u.email for u in result]
        assert emails == sorted(emails)

    def test_limit_truncates_result(
        self, db_session: Session, event: EventPost, users: list[User]
    ) -> None:
        for u in users:
            add_participant(event, u)
        db_session.flush()

        result = get_participants(event, limit=2)

        assert len(result) == 2

    def test_rejects_non_event_post(self, db_session: Session) -> None:
        # Guard the ``isinstance(event, EventPost)`` check at the top of
        # ``get_participants`` — passing something else must raise.
        with pytest.raises(TypeError, match="Expected EventPost"):
            get_participants("not an event")  # type: ignore[arg-type]
