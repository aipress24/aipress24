# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit-tier tests for `wip/services/sujet_notifications.py`.

The bulk of `notify_media_of_sujet_proposition` is orchestration
around the BW lookup, the SVCS NotificationService, and the
SujetPropositionNotificationMail send — those belong at b_integration.

What we CAN cover here without a DB session :

* `_pick_bw_owner_user` fallback branch — `get_active_business_wall_for_organisation`
  returns `None` for a transient `Organisation` (its `InstanceState.session`
  is `None`, see `bw_activation/user_utils.py` lines 161-163), so we land
  in the `media_org.members` iteration. Swap `members` for a plain list
  of stubs and we can pin the selection rules.
* `_pick_bw_owner_email` — thin wrapper, returns `""` for the no-owner
  case and `owner.email` for the happy path.

These tests stress the dispatch rules that production data shape
exercises every day. The DB-touching `_get_user_by_id` branch (used
when the org has an active BW) is left for b_integration.
"""

from __future__ import annotations

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wip.services.sujet_notifications import (
    _pick_bw_owner_email,
    _pick_bw_owner_user,
)


def _stub_member(*, active: bool, email: str) -> User:
    """Transient `User` — the function reads `.active` and `.email` ;
    a transient instance carries them without a DB session. We can't
    use a `SimpleNamespace` because `Organisation.members` is a
    SQLAlchemy relationship that runs append-events on assignment
    and the events require `_sa_instance_state`."""
    return User(email=email, active=active)


def _orphan_org(
    name: str = "Le Monde", *, members: list[User] | None = None
) -> Organisation:
    """Transient `Organisation` with `bw_id=None`. Two consequences :
    `inspect(org).session is None` so `get_active_business_wall_for_organisation`
    returns at its line 162 (« no session, no BW »), and the fallback
    members-iteration branch runs.

    Setting members via the relationship triggers back_populates →
    each user's `organisation` attr gets pointed at this org. Harmless
    for transient instances."""
    org = Organisation(name=name)
    org.bw_id = None
    if members:
        org.members = members
    return org


class TestPickBwOwnerUserFallback:
    """`_pick_bw_owner_user` fallback : when no active BW maps to the
    org, scan `media_org.members` for the first active user with an
    email."""

    def test_returns_none_when_org_has_no_members(self):
        org = _orphan_org()
        # `Organisation.members` defaults to an empty InstrumentedList
        # on a fresh instance — no override needed.
        assert _pick_bw_owner_user(org) is None

    def test_picks_first_active_member_with_email(self):
        target = _stub_member(active=True, email="boss@lemonde.fr")
        org = _orphan_org(members=[target])
        assert _pick_bw_owner_user(org) is target

    def test_skips_inactive_members(self):
        inactive = _stub_member(active=False, email="ghost@lemonde.fr")
        target = _stub_member(active=True, email="boss@lemonde.fr")
        org = _orphan_org(members=[inactive, target])
        assert _pick_bw_owner_user(org) is target

    def test_skips_members_without_email(self):
        no_email = _stub_member(active=True, email="")
        target = _stub_member(active=True, email="boss@lemonde.fr")
        org = _orphan_org(members=[no_email, target])
        assert _pick_bw_owner_user(org) is target

    def test_returns_first_match_not_a_better_one_later(self):
        """Order matters : the iteration commits on the first hit, even
        if a « better » candidate (rédacteur en chef, owner, etc.)
        appears later. Pin so a future reordering of `members` doesn't
        silently route notifications differently."""
        first = _stub_member(active=True, email="staff@lemonde.fr")
        second = _stub_member(active=True, email="boss@lemonde.fr")
        org = _orphan_org(members=[first, second])
        assert _pick_bw_owner_user(org) is first

    def test_returns_none_when_all_members_filtered_out(self):
        org = _orphan_org(
            members=[
                _stub_member(active=False, email="x@lemonde.fr"),
                _stub_member(active=True, email=""),
            ]
        )
        assert _pick_bw_owner_user(org) is None


class TestPickBwOwnerEmail:
    """Legacy `_pick_bw_owner_email` wrapper — kept for the few
    callsites that only need the email string. Should mirror
    `_pick_bw_owner_user` and degrade gracefully to `""`."""

    def test_returns_empty_string_for_orphan_org_with_no_members(self):
        assert _pick_bw_owner_email(_orphan_org()) == ""

    def test_returns_owner_email_when_found(self):
        org = _orphan_org(
            members=[_stub_member(active=True, email="boss@lemonde.fr")]
        )
        assert _pick_bw_owner_email(org) == "boss@lemonde.fr"

    def test_returns_empty_when_only_inactive_members(self):
        """An owner-less org should produce `""`, not the email of an
        inactive member. Pin so callsites using the wrapper as a
        truthiness check (`if email:`) keep working."""
        org = _orphan_org(
            members=[_stub_member(active=False, email="ghost@lemonde.fr")]
        )
        assert _pick_bw_owner_email(org) == ""
