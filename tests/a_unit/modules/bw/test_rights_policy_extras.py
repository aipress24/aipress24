# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the *DB-adjacent* helpers of
`app.modules.bw.bw_activation.rights_policy` that the existing
`test_cession_policy.py` doesn't cover.

Three concerns are pinned here :

1. The `_RIGHTS_HOLDER_BW_TYPES` module constant. The set of BW
   types that hold reproduction rights is a load-bearing business
   rule (see bug #0112) — anyone adding / removing an entry should
   trip a unit-test failure, not discover the change in production.

2. The pure prefix of `_buyer_media_bw_for` extracted as
   `_buyer_org_id_or_none(user)`. The function defensively returns
   None for a None user or a user without an organisation — that
   short-circuit must hold before any DB query is built.

3. The pure candidate-collection logic of `emitter_bw_for_post`
   extracted as `_collect_candidate_org_ids(post)`. The priority
   order (publisher → media → owner-org) is part of the policy
   contract — pin so a refactor reordering the candidates doesn't
   silently change which BW claims emitter status for a post.

These helpers are pure : no DB session, no Flask app context.
Tests pass plain stubs and assert on returned values (state),
never on internal interactions (behaviour). Per CLAUDE.md :
*"Don't use mocks. Prefer stubs."*
"""

from __future__ import annotations

import pytest

from app.modules.bw.bw_activation.rights_policy import (
    _RIGHTS_HOLDER_BW_TYPES,
    _buyer_org_id_or_none,
    _collect_candidate_org_ids,
)

# ── _RIGHTS_HOLDER_BW_TYPES — pin the load-bearing constant ──────────


class TestRightsHolderBwTypes:
    """The set of BW types that hold reproduction rights on their
    own content. See bug #0112 : `micro` is intentionally included
    so journalists-in-micro-entreprise own their production per the
    platform CGV."""

    def test_contains_media(self):
        """`media` is the canonical publisher BW. Pin."""
        assert "media" in _RIGHTS_HOLDER_BW_TYPES

    def test_contains_micro(self):
        """`micro` was added per bug #0112 — pin so a refactor
        that drops it (treating `micro` as a non-rights-holder)
        gets caught immediately."""
        assert "micro" in _RIGHTS_HOLDER_BW_TYPES

    def test_exact_membership(self):
        """Snapshot the full set. Adding a fourth rights-holder
        type is a deliberate decision — it MUST update this test."""
        assert set(_RIGHTS_HOLDER_BW_TYPES) == {"media", "micro"}

    def test_is_a_tuple_not_list(self):
        """Module-level constants of « set of valid options » are
        tuples (immutable) by convention. Pin so a future refactor
        doesn't turn this into a mutable list."""
        assert isinstance(_RIGHTS_HOLDER_BW_TYPES, tuple)

    def test_does_not_contain_pr(self):
        """A `pr` (press relations) BW is NOT a rights holder —
        a PR firm cannot sell reproduction licences on third-party
        content. Pin so a future refactor « simplifying » the rule
        doesn't silently widen the rights-holder set."""
        assert "pr" not in _RIGHTS_HOLDER_BW_TYPES

    def test_does_not_contain_agency(self):
        """`agency` and `corporate` are not rights holders in the
        MVP. Pin so future « let's allow agencies to sell » edits
        are conscious."""
        for bw_type in ("agency", "corporate", "academics", "edu"):
            assert bw_type not in _RIGHTS_HOLDER_BW_TYPES


# ── _buyer_org_id_or_none — pure prefix of _buyer_media_bw_for ───────


class _UserStub:
    """Stand-in for the User ORM row — only `organisation_id`
    matters for `_buyer_org_id_or_none`."""

    def __init__(self, organisation_id=None) -> None:
        self.organisation_id = organisation_id


class _BareUser:
    """Stand-in for a User-shaped object that has no
    `organisation_id` attribute at all. The defensive `getattr`
    must keep this from raising AttributeError."""


class TestBuyerOrgIdOrNone:
    """Pure prefix of `_buyer_media_bw_for` : the None-check + org
    extraction, no DB. The DB query branch is exercised by the
    b_integration suite."""

    def test_none_user_returns_none(self):
        """A None user must short-circuit before any attribute
        access. Pin so the SQL query never runs for anonymous
        users."""
        assert _buyer_org_id_or_none(None) is None

    def test_user_with_no_org_returns_none(self):
        """A user with `organisation_id = None` (e.g. a free-floating
        member) cannot have a buyer BW — no org → no BW."""
        user = _UserStub(organisation_id=None)
        assert _buyer_org_id_or_none(user) is None

    def test_user_with_int_org_returns_org_id(self):
        """The org id passes through verbatim — the SQL query
        builds `.where(organisation_id == org_id)`."""
        user = _UserStub(organisation_id=42)
        assert _buyer_org_id_or_none(user) == 42

    @pytest.mark.parametrize("org_id", [1, 99, 12345, 2**31 - 1])
    def test_various_int_org_ids_pass_through(self, org_id):
        user = _UserStub(organisation_id=org_id)
        assert _buyer_org_id_or_none(user) == org_id

    def test_user_without_org_attribute_returns_none(self):
        """A duck-typed user object lacking `organisation_id`
        entirely (an anonymous-user proxy, a test stub) must NOT
        raise AttributeError. Defensive `getattr` returns None.

        Pin so a future refactor that drops the defensive default
        and writes `user.organisation_id` directly is caught."""
        assert _buyer_org_id_or_none(_BareUser()) is None

    def test_zero_org_id_is_treated_as_falsy_but_not_none(self):
        """Edge case : an org_id of 0 is technically a valid int
        but conventionally not a real id. The helper only checks
        `is None`, so 0 passes through — pin the contract so a
        future « truthy check » regression that filters out 0
        is caught."""
        user = _UserStub(organisation_id=0)
        # 0 is not None — so it passes through.
        assert _buyer_org_id_or_none(user) == 0


# ── _collect_candidate_org_ids — pure prefix of emitter_bw_for_post ──


class _OwnerStub:
    """Stand-in for the Post.owner User — only `organisation_id`
    matters."""

    def __init__(self, organisation_id=None) -> None:
        self.organisation_id = organisation_id


class _PostStub:
    """Stand-in for a Post — three optional attributes drive
    candidate collection : `publisher_id`, `media_id`, `owner`."""

    def __init__(self, publisher_id=None, media_id=None, owner=None) -> None:
        self.publisher_id = publisher_id
        self.media_id = media_id
        self.owner = owner


class _BarePost:
    """A duck-typed post with no attributes at all — the defensive
    `getattr` must keep this from raising AttributeError."""


class TestCollectCandidateOrgIds:
    """Pure candidate-collection : pin the priority order
    publisher → media → owner-org. Snapshot the contract so a
    refactor doesn't silently change which BW claims emitter
    status for a post."""

    def test_empty_post_returns_empty_list(self):
        """A bare post with no publisher / media / owner yields
        no candidates → the caller skips the SQL query entirely."""
        assert _collect_candidate_org_ids(_BarePost()) == []

    def test_post_with_none_everywhere_returns_empty_list(self):
        post = _PostStub(publisher_id=None, media_id=None, owner=None)
        assert _collect_candidate_org_ids(post) == []

    def test_publisher_id_alone(self):
        post = _PostStub(publisher_id=10)
        assert _collect_candidate_org_ids(post) == [10]

    def test_media_id_alone(self):
        post = _PostStub(media_id=20)
        assert _collect_candidate_org_ids(post) == [20]

    def test_owner_org_alone(self):
        post = _PostStub(owner=_OwnerStub(organisation_id=30))
        assert _collect_candidate_org_ids(post) == [30]

    def test_priority_order_publisher_then_media_then_owner(self):
        """The contract : `publisher_id` first, then `media_id`,
        then `owner.organisation_id`. Pin so a refactor that
        reorders the candidates is caught — the SQL `limit(1)`
        means the first match wins."""
        post = _PostStub(
            publisher_id=10,
            media_id=20,
            owner=_OwnerStub(organisation_id=30),
        )
        assert _collect_candidate_org_ids(post) == [10, 20, 30]

    def test_publisher_and_media_only(self):
        """Owner None → only publisher + media collected."""
        post = _PostStub(publisher_id=10, media_id=20, owner=None)
        assert _collect_candidate_org_ids(post) == [10, 20]

    def test_publisher_and_owner_only(self):
        """Media None → publisher + owner-org collected, in
        publisher-then-owner order."""
        post = _PostStub(
            publisher_id=10,
            media_id=None,
            owner=_OwnerStub(organisation_id=30),
        )
        assert _collect_candidate_org_ids(post) == [10, 30]

    def test_owner_with_none_org_skipped(self):
        """An owner whose `organisation_id` is None must NOT add a
        None into the list — that would break the SQL `in_()`
        clause."""
        post = _PostStub(
            publisher_id=10,
            owner=_OwnerStub(organisation_id=None),
        )
        assert _collect_candidate_org_ids(post) == [10]

    def test_owner_without_org_attribute_skipped(self):
        """A duck-typed owner lacking `organisation_id` entirely
        must NOT raise AttributeError. Defensive `getattr` returns
        None → the owner is skipped."""

        class _BareOwner:
            pass

        post = _PostStub(publisher_id=10, owner=_BareOwner())
        assert _collect_candidate_org_ids(post) == [10]

    def test_returns_list_not_set(self):
        """Order matters (priority is observable). Pin that the
        return is an ordered list, not a set / frozenset."""
        post = _PostStub(publisher_id=10, media_id=20)
        result = _collect_candidate_org_ids(post)
        assert isinstance(result, list)

    def test_duplicate_org_ids_preserved(self):
        """If publisher_id == media_id == owner.organisation_id,
        the list contains the same id three times. The SQL `in_()`
        deduplicates server-side, so we keep the list semantics
        here — pin so a future « let's dedupe » edit is conscious."""
        post = _PostStub(
            publisher_id=7,
            media_id=7,
            owner=_OwnerStub(organisation_id=7),
        )
        assert _collect_candidate_org_ids(post) == [7, 7, 7]

    @pytest.mark.parametrize(
        ("publisher_id", "media_id", "owner_org", "expected"),
        [
            # Single source.
            (1, None, None, [1]),
            (None, 2, None, [2]),
            (None, None, 3, [3]),
            # Two sources.
            (1, 2, None, [1, 2]),
            (1, None, 3, [1, 3]),
            (None, 2, 3, [2, 3]),
            # All three.
            (1, 2, 3, [1, 2, 3]),
            # Empty.
            (None, None, None, []),
        ],
    )
    def test_combinations(
        self,
        publisher_id,
        media_id,
        owner_org,
        expected,
    ):
        """Snapshot every combination of present / absent
        candidate sources. A refactor changing any branch is
        caught."""
        owner = _OwnerStub(organisation_id=owner_org) if owner_org else None
        post = _PostStub(
            publisher_id=publisher_id,
            media_id=media_id,
            owner=owner,
        )
        assert _collect_candidate_org_ids(post) == expected
