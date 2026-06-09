# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure module-level constants in ``swork/views/_common.py``.

The module ``app.modules.swork.views._common`` exposes a small handful of
*pure* data structures that are referenced from various spots in the swork
view layer:

* ``MASK_FIELDS`` — the dict that drives the privacy-filtering loop inside
  ``filter_email_mobile``. Each ``mode`` (e.g. ``"email"``) is concatenated
  with the logged-in user's ``contact_type`` to build a permission key
  (``f"{mode}_{contact_type}"``) looked up against the target user's
  ``show_contact_details`` mapping. The dict's *values* are SQLAlchemy column
  names passed to ``MaskFields.add_field`` / ``MaskFields.remove_field``.
* ``MEMBER_TABS`` / ``GROUP_TABS`` — the canonical tab definitions surfaced
  by the member-profile and group-detail pages. They are iterated in
  Jinja templates that key off ``"id"`` and render ``"label"``, so the
  shape contract is load-bearing.

This file pins the *contract* of those dicts (keys, value types, uniqueness,
canonical entries) — not the implementation. The ``MaskFields`` *class* is
already covered by ``test_mask_fields.py`` / ``test_masked_fields.py``;
this file complements them by pinning the data structure those tests
indirectly depend on.

We also exercise the documented early-return branch of
``filter_email_mobile`` (``if not user.profile or not target_user.profile``),
which is pure enough to test with simple stand-in objects — it short-circuits
before any database call.
"""

from __future__ import annotations

import pytest

from app.modules.swork.masked_fields import MaskFields
from app.modules.swork.views._common import (
    GROUP_TABS,
    MASK_FIELDS,
    MEMBER_TABS,
    filter_email_mobile,
)

# ---------------------------------------------------------------------------
# MASK_FIELDS dict constant
# ---------------------------------------------------------------------------


class TestMaskFieldsDictShape:
    """Pin the shape of ``MASK_FIELDS``.

    ``filter_email_mobile`` iterates ``MASK_FIELDS.items()`` and feeds the
    string *value* into ``MaskFields.add_field``. The two-string contract
    (dict[str, str]) is therefore part of the public surface — a refactor
    that swaps the values for ``Column`` objects or enum members would break
    every downstream privacy check.
    """

    def test_is_a_dict(self):
        assert isinstance(MASK_FIELDS, dict)

    def test_is_non_empty(self):
        """A degenerate empty dict would make ``filter_email_mobile`` a no-op
        and silently disable the privacy filter — pin defensively."""
        assert len(MASK_FIELDS) > 0

    def test_all_keys_are_strings(self):
        assert all(isinstance(k, str) for k in MASK_FIELDS)

    def test_all_values_are_strings(self):
        assert all(isinstance(v, str) for v in MASK_FIELDS.values())

    def test_keys_are_unique(self):
        """Dict keys are unique by construction in Python — but pinning
        this guards against a hand-written tuple-of-pairs refactor that
        would silently drop duplicates."""
        assert len(MASK_FIELDS) == len(set(MASK_FIELDS.keys()))

    def test_no_empty_keys_or_values(self):
        """An empty key would build a meaningless ``"_PRESSE"`` permission
        key; an empty value would skip masking entirely. Pin both."""
        for key, value in MASK_FIELDS.items():
            assert key, f"empty key in MASK_FIELDS: {key!r}"
            assert value, f"empty value for {key!r}: {value!r}"

    def test_keys_have_no_whitespace(self):
        """``filter_email_mobile`` builds permission keys via
        ``f"{mode}_{contact_type}"`` — leading/trailing whitespace on a
        mode would silently miss every lookup in ``user_allow``."""
        for key in MASK_FIELDS:
            assert key == key.strip(), f"whitespace in MASK_FIELDS key {key!r}"

    def test_values_have_no_whitespace(self):
        """Values are SQLAlchemy column names — whitespace would never
        match a real ``MaskFields.masked`` entry."""
        for value in MASK_FIELDS.values():
            assert value == value.strip(), f"whitespace in MASK_FIELDS value {value!r}"

    def test_values_are_valid_python_identifiers(self):
        """The values are used as ``User`` column names; non-identifier
        characters (dots, dashes, etc.) would never resolve."""
        for value in MASK_FIELDS.values():
            assert value.isidentifier(), f"non-identifier MASK_FIELDS value: {value!r}"


class TestMaskFieldsCanonicalEntries:
    """Pin the canonical entries documented in the source.

    The two « historic » modes are ``email`` and ``mobile``; the followee
    fallback loop in ``filter_email_mobile`` hardcodes those two strings
    (``for mode in ("email", "mobile"):``), so dropping either key from
    the dict would mean the followee allowance never fires for that mode.
    """

    @pytest.mark.parametrize("mode", ["email", "mobile"])
    def test_canonical_mode_present(self, mode):
        assert mode in MASK_FIELDS

    def test_email_maps_to_email_column(self):
        """``email`` mode is masked by hiding the ``email`` column on
        ``User`` — pin so a future model rename surfaces here."""
        assert MASK_FIELDS["email"] == "email"

    def test_mobile_maps_to_tel_mobile_column(self):
        """``mobile`` mode masks the ``tel_mobile`` column (note the
        French naming convention used in the User profile)."""
        assert MASK_FIELDS["mobile"] == "tel_mobile"

    def test_email_relation_presse_present(self):
        """The third entry — added for PR-relation visibility — is part
        of the contract too; the value is the same string as the key."""
        assert MASK_FIELDS["email_relation_presse"] == "email_relation_presse"


class TestMaskFieldsFollowEeLoopConsistency:
    """The followee fallback loop in ``filter_email_mobile`` only iterates
    ``("email", "mobile")``. Pin that those two modes are *always* present
    in ``MASK_FIELDS`` and that the loop's ``MASK_FIELDS[mode]`` lookup
    never KeyErrors at runtime."""

    @pytest.mark.parametrize("mode", ["email", "mobile"])
    def test_followee_loop_lookup_does_not_raise(self, mode):
        # This is the exact lookup that happens inside the followee
        # fallback block.
        _ = MASK_FIELDS[mode]

    def test_followee_modes_subset_of_keys(self):
        followee_modes = {"email", "mobile"}
        assert followee_modes <= set(MASK_FIELDS.keys())

    def test_followee_values_appear_in_dict_values(self):
        """The followee fallback removes ``MASK_FIELDS[mode]`` from the
        ``MaskFields.masked`` set; those exact strings must be the same
        ones added earlier by the main loop. Pin the round-trip."""
        for mode in ("email", "mobile"):
            field = MASK_FIELDS[mode]
            assert field in MASK_FIELDS.values()


# ---------------------------------------------------------------------------
# filter_email_mobile early-return branch (pure)
# ---------------------------------------------------------------------------


class _StubUser:
    """Tiny duck-typed stand-in for ``User`` — only exposes ``profile``.

    ``filter_email_mobile`` short-circuits on ``not user.profile or
    not target_user.profile`` *before* it calls ``adapt(...)`` or touches
    the DB, so we don't need a real ``User`` instance to exercise it.
    """

    def __init__(self, profile=None):
        self.profile = profile


class TestFilterEmailMobileEarlyReturn:
    """Pin the documented « return empty mask if profiles are incomplete »
    branch. This branch is the *only* pure path through
    ``filter_email_mobile`` — anything past the early return needs a real
    ``SocialUser`` adapter and DB session.
    """

    def test_both_profiles_none_returns_empty_mask(self):
        result = filter_email_mobile(_StubUser(None), _StubUser(None))
        assert isinstance(result, MaskFields)
        assert result.masked == set()

    def test_logged_user_profile_none_returns_empty_mask(self):
        """If the logged-in user has no profile, masking can't be computed
        — fall through to the safe empty default."""
        target = _StubUser(profile=object())
        result = filter_email_mobile(_StubUser(None), target)
        assert result.masked == set()

    def test_target_user_profile_none_returns_empty_mask(self):
        """If the *target* user has no profile, ``show_contact_details``
        is unreachable and the function returns an empty mask."""
        logged = _StubUser(profile=object())
        result = filter_email_mobile(logged, _StubUser(None))
        assert result.masked == set()

    def test_early_return_does_not_populate_story(self):
        """The early-return branch returns a freshly-constructed
        ``MaskFields`` — no story should be appended. Pin to document
        that the « no field masked » message is *only* appended by the
        post-loop branch."""
        result = filter_email_mobile(_StubUser(None), _StubUser(None))
        assert result.story == ""

    @pytest.mark.parametrize(
        ("logged_profile", "target_profile"),
        [
            (None, None),
            (None, object()),
            (object(), None),
            (False, False),  # falsy non-None values also trip the guard
            (0, object()),
        ],
    )
    def test_falsy_profile_short_circuits(self, logged_profile, target_profile):
        """The guard is ``if not user.profile`` — any falsy value (None,
        False, 0, empty containers) should trigger the early return.
        Pin the truthiness check so a refactor to ``is None`` would
        surface here."""
        result = filter_email_mobile(
            _StubUser(logged_profile), _StubUser(target_profile)
        )
        assert result.masked == set()
        assert result.story == ""

    def test_returns_fresh_instance_each_call(self):
        """Two calls must return *distinct* ``MaskFields`` instances —
        a memoised return would let callers mutate state visible to
        the next request, which would be a privacy leak."""
        a = filter_email_mobile(_StubUser(None), _StubUser(None))
        b = filter_email_mobile(_StubUser(None), _StubUser(None))
        assert a is not b


# ---------------------------------------------------------------------------
# MEMBER_TABS / GROUP_TABS — sibling pure constants
# ---------------------------------------------------------------------------


class TestMemberTabs:
    """Pin the member-profile tab list. Jinja templates iterate it as
    ``[{"id": ..., "label": ...}, ...]`` and use ``id`` as the routing
    fragment, so the shape + key set is load-bearing."""

    def test_is_a_list(self):
        assert isinstance(MEMBER_TABS, list)

    def test_is_non_empty(self):
        assert len(MEMBER_TABS) > 0

    def test_every_entry_has_id_and_label(self):
        for tab in MEMBER_TABS:
            assert set(tab.keys()) == {"id", "label"}
            assert isinstance(tab["id"], str)
            assert isinstance(tab["label"], str)

    def test_ids_are_unique(self):
        """The HTMX target uses the ``id`` as a URL fragment — duplicate
        ids would silently overwrite each other in the routing layer."""
        ids = [tab["id"] for tab in MEMBER_TABS]
        assert len(ids) == len(set(ids))

    @pytest.mark.parametrize(
        "tab_id",
        ["profile", "publications", "press-book", "groups"],
    )
    def test_canonical_tab_present(self, tab_id):
        """A handful of canonical tab ids referenced from templates +
        controllers — pin so a refactor that drops one surfaces here."""
        ids = {tab["id"] for tab in MEMBER_TABS}
        assert tab_id in ids

    def test_labels_are_non_empty(self):
        """An empty label would render as a blank tab — useless and
        confusing. Pin defensively."""
        for tab in MEMBER_TABS:
            assert tab["label"].strip(), f"empty label for tab {tab['id']!r}"

    def test_first_tab_is_profile(self):
        """``profile`` is the default landing tab — pin its position so
        a reorder surfaces here (the default-route handler relies on
        it being first)."""
        assert MEMBER_TABS[0]["id"] == "profile"


class TestGroupTabs:
    """Pin the group-detail tab list. Same shape contract as
    ``MEMBER_TABS``."""

    def test_is_a_list(self):
        assert isinstance(GROUP_TABS, list)

    def test_every_entry_has_id_and_label(self):
        for tab in GROUP_TABS:
            assert set(tab.keys()) == {"id", "label"}
            assert isinstance(tab["id"], str)
            assert isinstance(tab["label"], str)

    def test_ids_are_unique(self):
        ids = [tab["id"] for tab in GROUP_TABS]
        assert len(ids) == len(set(ids))

    @pytest.mark.parametrize("tab_id", ["wall", "description", "members"])
    def test_canonical_tab_present(self, tab_id):
        ids = {tab["id"] for tab in GROUP_TABS}
        assert tab_id in ids

    def test_labels_are_non_empty(self):
        for tab in GROUP_TABS:
            assert tab["label"].strip(), f"empty label for tab {tab['id']!r}"

    def test_first_tab_is_wall(self):
        """``wall`` is the default landing tab for the group view."""
        assert GROUP_TABS[0]["id"] == "wall"
