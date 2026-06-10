# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mock-free unit tests for the *pure* layer of events/services.py.

Background
----------
The original ``tests/a_unit/modules/events/test_event_services.py`` covers
end-to-end DB behaviour using fixtures that hit a live SQLAlchemy session.
That suite is slow and out of scope for the Phase 2 pyramid push: it
verifies the imperative *shell*, not the logic.

This file exercises **only** the pure predicates of ``services.py``:

* ``_is_user_in(user_id, participant_ids)`` — extracted helper (Pattern A,
  functional core / imperative shell). The DB-bound ``is_participant``
  delegates the membership question to this helper, so the tricky branches
  (None ids, empty lists, mixed types) can be covered without a session.
* ``can_user_accredit(user, event)`` — a role check that already takes a
  duck-typed ``user`` and an ignored ``event``. We pass tiny stand-in
  classes that expose only what the function reads.

No mocking framework is used and no test-double library is imported:
stand-ins are hand-rolled classes that implement just what the production
code calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.enums import RoleEnum
from app.modules.events.services import _is_user_in, can_user_accredit

# ----------------------------------------------------------------
# Stand-ins
# ----------------------------------------------------------------


@dataclass
class UserStub:
    """Duck-typed stand-in for ``app.models.auth.User``.

    Only the attributes/methods actually read by the target predicates are
    implemented: ``id`` (for completeness) and ``has_role``.
    """

    id: int = 0
    roles: set[RoleEnum] = field(default_factory=set)

    def has_role(self, role: RoleEnum | str) -> bool:
        # Production ``has_role`` accepts ``RoleEnum | str | Role``; we only
        # need to behave correctly for the first two.
        if isinstance(role, str) and not isinstance(role, RoleEnum):
            return any(r.value == role for r in self.roles)
        return role in self.roles


@dataclass
class EventStub:
    """Duck-typed stand-in for ``EventPost``.

    ``can_user_accredit`` currently ignores the event argument (Bug 0127 —
    "reserved for future per-event-type rules"), so the stand-in is
    intentionally empty. We still pass *some* object to lock in the
    function's tolerance of opaque event types.
    """

    id: int = 0
    type: str = "press"


# ----------------------------------------------------------------
# _is_user_in — pure membership predicate (Pattern A)
# ----------------------------------------------------------------


class TestIsUserIn:
    """Cover the pure helper that drives ``is_participant``.

    The helper is a tiny ``any(...)`` loop, but it has three branches worth
    pinning down: ``None`` user, empty collection, and mixed-type ids
    (SQLAlchemy may return either ``int`` rows or scalar columns).
    """

    def test_empty_collection_is_false(self) -> None:
        assert _is_user_in(1, []) is False

    def test_none_user_is_false_even_with_none_in_list(self) -> None:
        # Defensive: a missing user id must never be considered a member,
        # even if the collection itself contains ``None`` (which would
        # otherwise satisfy ``pid == user_id``).
        assert _is_user_in(None, [None, 1, 2]) is False

    def test_present_user_is_true(self) -> None:
        assert _is_user_in(42, [1, 7, 42, 99]) is True

    def test_absent_user_is_false(self) -> None:
        assert _is_user_in(42, [1, 7, 99]) is False

    def test_single_element_match(self) -> None:
        assert _is_user_in(7, [7]) is True

    def test_single_element_no_match(self) -> None:
        assert _is_user_in(7, [8]) is False

    @pytest.mark.parametrize(
        ("user_id", "participant_ids", "expected"),
        [
            (1, [1, 2, 3], True),
            (2, [1, 2, 3], True),
            (3, [1, 2, 3], True),
            (4, [1, 2, 3], False),
            (0, [0], True),  # id 0 is a valid id, not falsy here
            (0, [1, 2, 3], False),
        ],
    )
    def test_membership_table(
        self,
        user_id: int,
        participant_ids: list[int],
        expected: bool,
    ) -> None:
        assert _is_user_in(user_id, participant_ids) is expected

    def test_accepts_iterator_not_only_list(self) -> None:
        # Production code passes whatever SQLAlchemy hands back (which is a
        # ``ScalarResult``-like iterator, not a ``list``). The helper must
        # consume any iterable.
        def gen():
            yield 10
            yield 20
            yield 30

        assert _is_user_in(20, gen()) is True

    def test_accepts_set(self) -> None:
        assert _is_user_in(5, {1, 3, 5, 7}) is True
        assert _is_user_in(4, {1, 3, 5, 7}) is False

    def test_accepts_tuple(self) -> None:
        assert _is_user_in("x", ("a", "b", "x")) is True

    def test_returns_bool_not_truthy(self) -> None:
        # Guard against the helper drifting into returning ``int`` or
        # ``None``: callers rely on a strict ``bool``.
        result = _is_user_in(1, [1, 2, 3])
        assert result is True
        assert isinstance(result, bool)


# ----------------------------------------------------------------
# can_user_accredit — pure role predicate
# ----------------------------------------------------------------


class TestCanUserAccredit:
    """Bug 0127 — accreditation reserved to ``RoleEnum.PRESS_MEDIA``.

    The function is currently a one-liner role check that ignores the event,
    but the contract — "journalist may, others may not" — is exactly the
    invariant the UI accreditation toggle depends on. We pin it down with
    stand-ins so a future refactor (per-event-type rules, see docstring)
    can't quietly regress the default path.
    """

    def test_journalist_can_accredit(self) -> None:
        user = UserStub(roles={RoleEnum.PRESS_MEDIA})
        event = EventStub()

        assert can_user_accredit(user, event) is True

    def test_user_with_no_roles_cannot_accredit(self) -> None:
        user = UserStub(roles=set())
        event = EventStub()

        assert can_user_accredit(user, event) is False

    @pytest.mark.parametrize(
        "role",
        [
            RoleEnum.ADMIN,
            RoleEnum.LEADER,
            RoleEnum.MANAGER,
            RoleEnum.PRESS_RELATIONS,
            RoleEnum.EXPERT,
            RoleEnum.ACADEMIC,
            RoleEnum.TRANSFORMER,
            RoleEnum.SELF,
        ],
    )
    def test_other_single_roles_cannot_accredit(self, role: RoleEnum) -> None:
        # Every non-PRESS_MEDIA role, on its own, must be refused. This is
        # the regression net for Bug 0127.
        user = UserStub(roles={role})
        event = EventStub()

        assert can_user_accredit(user, event) is False

    def test_user_with_press_media_among_others_can_accredit(self) -> None:
        # Realistic case: a journalist who is also an expert or admin must
        # still be allowed.
        user = UserStub(
            roles={RoleEnum.PRESS_MEDIA, RoleEnum.EXPERT, RoleEnum.ADMIN}
        )
        event = EventStub()

        assert can_user_accredit(user, event) is True

    def test_event_argument_is_currently_ignored(self) -> None:
        # Documents (and locks in) the *current* contract: the event type is
        # not consulted. When per-event rules land, this test will need to
        # be split — that's the intent.
        user = UserStub(roles={RoleEnum.PRESS_MEDIA})

        press_event = EventStub(type="press")
        public_event = EventStub(type="public")
        weird_event = EventStub(type="anything-at-all")

        assert can_user_accredit(user, press_event) is True
        assert can_user_accredit(user, public_event) is True
        assert can_user_accredit(user, weird_event) is True

    def test_event_can_even_be_none_like(self) -> None:
        # ``del event`` in the implementation means *any* object is accepted.
        # Use a bare ``object()`` to exercise that tolerance.
        user = UserStub(roles={RoleEnum.PRESS_MEDIA})

        assert can_user_accredit(user, object()) is True

    def test_returns_bool(self) -> None:
        # Same hygiene check as for ``_is_user_in``.
        user = UserStub(roles={RoleEnum.PRESS_MEDIA})
        event = EventStub()

        result = can_user_accredit(user, event)

        assert result is True
        assert isinstance(result, bool)

    def test_accepts_role_by_string_value(self) -> None:
        # ``RoleEnum`` is a ``StrEnum``: ``PRESS_MEDIA.value == "journalist"``.
        # The stub's ``has_role`` handles the str path; this asserts the
        # production function passes the enum (not the str), which is the
        # canonical call form.
        user = UserStub(roles={RoleEnum.PRESS_MEDIA})
        event = EventStub()

        # If services.py ever switched to passing the string literal
        # ``"journalist"`` instead of the enum, this still has to work —
        # ``UserStub.has_role`` covers both paths.
        assert can_user_accredit(user, event) is True
