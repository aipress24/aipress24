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

from app.enums import CommunityEnum, RoleEnum
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

    ``can_user_accredit`` reads the event's ``audience`` since lot L3 —
    the argument it used to throw away with a ``del``.
    """

    id: int = 0
    type: str = "press"
    owner_id: int = -1
    audience: list[str] = field(default_factory=list)


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
    """RG-05 — le droit de demander se lit sur le **ciblage**, plus sur
    le rôle.

    Cette classe épinglait l'inverse : « journaliste oui, les autres
    non », sur tous les événements. C'était l'écart E1 de
    `specs/events-ecarts.md` — le livré interdisait à un universitaire
    de s'inscrire à un webinaire académique, et aucune spécification ne
    le demandait. Son propre commentaire l'anticipait : « When
    per-event rules land, this test will need to be split — that's the
    intent. » C'est fait.
    """

    def test_an_untargeted_event_is_open_to_everyone(self) -> None:
        event = EventStub(audience=[])

        for roles in ({RoleEnum.PRESS_MEDIA}, {RoleEnum.ACADEMIC}, set()):
            assert can_user_accredit(UserStub(roles=roles), event) is True

    def test_a_targeted_event_admits_its_communities(self) -> None:
        event = EventStub(audience=[CommunityEnum.PRESS_MEDIA.value])

        assert can_user_accredit(UserStub(roles={RoleEnum.PRESS_MEDIA}), event) is True

    def test_a_targeted_event_refuses_the_others(self) -> None:
        event = EventStub(audience=[CommunityEnum.PRESS_MEDIA.value])

        for role in (RoleEnum.ACADEMIC, RoleEnum.EXPERT, RoleEnum.TRANSFORMER):
            assert can_user_accredit(UserStub(roles={role}), event) is False

    def test_several_targeted_communities_are_a_disjunction(self) -> None:
        event = EventStub(
            audience=[
                CommunityEnum.PRESS_MEDIA.value,
                CommunityEnum.ACADEMICS.value,
            ]
        )

        assert can_user_accredit(UserStub(roles={RoleEnum.ACADEMIC}), event) is True
        assert can_user_accredit(UserStub(roles={RoleEnum.EXPERT}), event) is False

    def test_a_member_of_several_communities_needs_only_one_match(self) -> None:
        event = EventStub(audience=[CommunityEnum.PRESS_MEDIA.value])
        user = UserStub(roles={RoleEnum.PRESS_MEDIA, RoleEnum.EXPERT, RoleEnum.ADMIN})

        assert can_user_accredit(user, event) is True

    def test_a_user_without_any_community_role_is_refused_when_targeted(self) -> None:
        """Un administrateur n'a pas de rôle de communauté. Il ne doit
        pas être accrédité d'office — mais il ne doit pas non plus
        faire lever quoi que ce soit : c'est le piège
        `User.first_community()`, qui lèverait `RuntimeError`."""
        event = EventStub(audience=[CommunityEnum.PRESS_MEDIA.value])

        assert can_user_accredit(UserStub(roles={RoleEnum.ADMIN}), event) is False
        assert can_user_accredit(UserStub(roles=set()), event) is False

    def test_an_unknown_community_value_matches_nobody(self) -> None:
        """Une valeur périmée en base — après un renommage de
        `CommunityEnum` — ne doit ni ouvrir l'événement ni le faire
        planter."""
        event = EventStub(audience=["Une communauté qui n'existe plus"])

        assert can_user_accredit(UserStub(roles={RoleEnum.PRESS_MEDIA}), event) is False

    def test_returns_bool(self) -> None:
        result = can_user_accredit(UserStub(roles=set()), EventStub(audience=[]))
        assert isinstance(result, bool)
