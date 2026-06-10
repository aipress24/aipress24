# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure helpers behind Stage B6 (PR Manager
permissions UI).

Stage B6 ``assign_missions`` is the wizard step where the BW Owner /
Manager hands a set of fine-grained permissions to each PR Manager
(press-release publishing, events, missions, etc.). The route itself
is I/O-heavy (session, request.form, db.session, redirects) but the
*decisions* it makes — what counts as granted, what flipped, where to
redirect — are pure functions of plain dicts and strings.

This file pins those pure helpers so :

- A typo in the form-field whitelist (``mission_press_release`` etc.)
  is caught at PR time rather than at first end-user POST. The HTML
  template and the Python parser must agree on the *exact* checkbox
  names; the round-trip test below acts as the contract.
- The « what changed » diff is symmetric — a key that switches
  ``False → True`` lands in ``granted``, the reverse in ``revoked``,
  and a no-op key lands in neither. Missing keys default to ``False``
  on either side (checkboxes don't POST when unchecked).
- The « previous » endpoint branches on ``bw_type == "pr"`` only;
  every other BW type goes to the external-partners step.
- The action whitelist is exactly ``{previous, finish}`` — any other
  value is a programmer error and the route surfaces it as
  ``ValueError``.

All tests are mock-free : plain dicts stand in for ``request.form``
(Mapping[str, Any]) and plain strings for the bw_type / action knobs.
"""

from __future__ import annotations

import pytest

from app.modules.bw.bw_activation.models.role import PermissionType
from app.modules.bw.bw_activation.routes.stage_b6 import (
    _FORM_TO_PERMISSION,
    _VALID_ACTIONS,
    diff_missions,
    is_valid_action,
    parse_missions_from_form,
    resolve_previous_endpoint,
)

# Canonical list of the 7 permission values the B6 form drives.
# Kept in sync with `_FORM_TO_PERMISSION` (see TestFormToPermissionMap
# below for the round-trip).
PERMISSION_VALUES = [
    PermissionType.PRESS_RELEASE.value,
    PermissionType.EVENTS.value,
    PermissionType.MISSIONS.value,
    PermissionType.PROJECTS.value,
    PermissionType.INTERNSHIPS.value,
    PermissionType.APPRENTICESHIPS.value,
    PermissionType.DOCTORAL.value,
]


class TestParseMissionsFromForm:
    """``parse_missions_from_form`` translates a request.form mapping
    into the canonical missions dict persisted on ``BusinessWall.missions``.

    The helper is the seam between « HTML checkbox name » and
    « PermissionType value » — getting it wrong silently drops
    permissions at the next save (the row goes back to False).
    """

    def test_empty_form_yields_all_false(self):
        """A POST with no checkboxes ticked (so no mission_* keys in
        the form) must produce all-False — Flask's request.form omits
        unchecked HTML checkboxes entirely. Tests would catch a
        regression where the parser starts defaulting to True."""
        result = parse_missions_from_form({})
        assert set(result.keys()) == set(PERMISSION_VALUES)
        assert all(value is False for value in result.values())

    def test_all_checked_yields_all_true(self):
        """Every checkbox ticked in the UI sends ``"on"`` (Flask's
        default for HTML checkboxes). Pin that every permission
        flips to True with the production form encoding."""
        form = dict.fromkeys(_FORM_TO_PERMISSION, "on")
        result = parse_missions_from_form(form)
        assert all(value is True for value in result.values())
        # And only the 7 known permissions — no leak of unrelated form fields.
        assert set(result.keys()) == set(PERMISSION_VALUES)

    def test_only_press_release_checked(self):
        """A realistic partial-grant scenario : the BW Owner grants
        press-release publishing only. Pin the per-key isolation so
        a regression where one checkbox name accidentally drives
        another permission is caught."""
        form = {"mission_press_release": "on"}
        result = parse_missions_from_form(form)
        assert result[PermissionType.PRESS_RELEASE.value] is True
        for value in PERMISSION_VALUES:
            if value != PermissionType.PRESS_RELEASE.value:
                assert result[value] is False

    @pytest.mark.parametrize(
        ("field", "permission"),
        sorted(_FORM_TO_PERMISSION.items()),
    )
    def test_each_field_drives_its_own_permission(self, field, permission):
        """Round-trip every (form field -> permission) pair. Catches
        a copy-paste mistake where two fields accidentally drive the
        same permission, or where a typo in the field name leaves
        the corresponding permission stuck at False."""
        result = parse_missions_from_form({field: "on"})
        assert result[permission] is True
        # No other permission spuriously flipped.
        others = [v for v in PERMISSION_VALUES if v != permission]
        for other in others:
            assert result[other] is False

    @pytest.mark.parametrize(
        "truthy",
        ["on", "1", "yes", "true", "checked"],
    )
    def test_any_truthy_string_is_true(self, truthy):
        """The parser uses ``bool(form.get(...))`` so any non-empty
        string flips the permission to True. HTML checkboxes default
        to ``"on"`` but pin the broader contract — a future template
        change to ``value="1"`` must not silently break the parser."""
        result = parse_missions_from_form({"mission_events": truthy})
        assert result[PermissionType.EVENTS.value] is True

    @pytest.mark.parametrize(
        "falsy",
        ["", None],
    )
    def test_empty_or_none_value_is_false(self, falsy):
        """Empty string and ``None`` (key absent / explicit None)
        must collapse to False — otherwise an oddly-rendered form
        would silently flip a permission on."""
        result = parse_missions_from_form({"mission_events": falsy})
        assert result[PermissionType.EVENTS.value] is False

    def test_unknown_form_keys_are_ignored(self):
        """Extra fields in the form (e.g. ``action`` button, CSRF
        token, browser autofill) must not appear in the missions
        dict — the parser whitelists only the 7 known mission_*
        fields. Catches a regression where the parser starts
        round-tripping unknown keys."""
        form = {
            "mission_press_release": "on",
            "action": "finish",
            "csrf_token": "deadbeef",
            "random_browser_field": "xyz",
        }
        result = parse_missions_from_form(form)
        assert set(result.keys()) == set(PERMISSION_VALUES)
        assert "action" not in result
        assert "csrf_token" not in result

    def test_result_keys_are_permission_type_values_not_field_names(self):
        """The output dict is keyed by the canonical
        ``PermissionType`` values (lowercase, snake_case) — never by
        the HTML field name (``mission_*`` prefix). Pin this so the
        persisted ``BusinessWall.missions`` schema doesn't drift to
        the form-encoding namespace."""
        result = parse_missions_from_form({"mission_press_release": "on"})
        assert "press_release" in result
        assert "mission_press_release" not in result


class TestFormToPermissionMap:
    """The static ``_FORM_TO_PERMISSION`` mapping is the contract
    between the B06 HTML template and the parser. Pin its shape so
    a refactor that drops or adds an entry is loud."""

    def test_covers_exactly_seven_permissions(self):
        """The B6 wizard exposes exactly 7 permission checkboxes —
        the three education-contract permissions (internships,
        apprenticeships, doctoral) plus press_release, events,
        missions, projects. MEDIA_CONTACTS / STATS_KPI / MESSAGES
        exist in the enum but are *not* wired to the B6 form."""
        assert len(_FORM_TO_PERMISSION) == 7

    def test_every_field_name_starts_with_mission_prefix(self):
        """The shared prefix is how the form template groups the
        checkboxes (and how a future parser can pick them out
        without an explicit whitelist). Catches an accidental
        rename that breaks the convention."""
        for field in _FORM_TO_PERMISSION:
            assert field.startswith("mission_")

    def test_values_are_unique(self):
        """Two HTML fields driving the same permission would be a
        copy-paste bug — the second checkbox would silently
        overwrite the first."""
        values = list(_FORM_TO_PERMISSION.values())
        assert len(values) == len(set(values))

    def test_values_are_all_valid_permission_types(self):
        """Every value must be a real ``PermissionType`` member —
        otherwise the parser writes garbage into
        ``BusinessWall.missions``."""
        valid = {m.value for m in PermissionType}
        for value in _FORM_TO_PERMISSION.values():
            assert value in valid


class TestDiffMissions:
    """``diff_missions`` is the « what changed » helper used (or
    usable) to drive notifications when a PR Manager's scope
    shrinks or grows. Pin its semantics."""

    def test_identical_states_no_changes(self):
        """No-op POST: same missions in, same missions out. Both
        sets must be empty — not None, not a set containing
        unchanged keys."""
        before = {PermissionType.EVENTS.value: True}
        after = {PermissionType.EVENTS.value: True}
        granted, revoked = diff_missions(before, after)
        assert granted == set()
        assert revoked == set()

    def test_grant_only(self):
        """False -> True for one key. Only ``granted`` is populated;
        ``revoked`` stays empty."""
        before = {PermissionType.EVENTS.value: False}
        after = {PermissionType.EVENTS.value: True}
        granted, revoked = diff_missions(before, after)
        assert granted == {PermissionType.EVENTS.value}
        assert revoked == set()

    def test_revoke_only(self):
        """True -> False for one key. Only ``revoked`` is populated."""
        before = {PermissionType.EVENTS.value: True}
        after = {PermissionType.EVENTS.value: False}
        granted, revoked = diff_missions(before, after)
        assert granted == set()
        assert revoked == {PermissionType.EVENTS.value}

    def test_grant_and_revoke_simultaneously(self):
        """A realistic edit : the BW Owner trades events for press
        releases. Both sets carry one item — symmetric."""
        before = {
            PermissionType.EVENTS.value: True,
            PermissionType.PRESS_RELEASE.value: False,
        }
        after = {
            PermissionType.EVENTS.value: False,
            PermissionType.PRESS_RELEASE.value: True,
        }
        granted, revoked = diff_missions(before, after)
        assert granted == {PermissionType.PRESS_RELEASE.value}
        assert revoked == {PermissionType.EVENTS.value}

    def test_missing_key_in_before_treated_as_false(self):
        """A key absent from ``before`` (e.g. a new permission rolled
        out after the row was created) must be treated as False —
        a True in ``after`` then registers as a grant, not as a no-op."""
        before: dict[str, bool] = {}
        after = {PermissionType.EVENTS.value: True}
        granted, revoked = diff_missions(before, after)
        assert granted == {PermissionType.EVENTS.value}
        assert revoked == set()

    def test_missing_key_in_after_treated_as_false(self):
        """A key absent from ``after`` (the parser always emits the
        full 7-key dict, but a caller might pass a partial state)
        is treated as False — True in ``before`` then registers
        as a revocation."""
        before = {PermissionType.EVENTS.value: True}
        after: dict[str, bool] = {}
        granted, revoked = diff_missions(before, after)
        assert granted == set()
        assert revoked == {PermissionType.EVENTS.value}

    def test_full_seven_keys_no_change(self):
        """The realistic « POST identical state » case : full 7-key
        dicts on both sides, all False. Pin that no spurious keys
        appear in either output set."""
        before = dict.fromkeys(PERMISSION_VALUES, False)
        after = dict.fromkeys(PERMISSION_VALUES, False)
        granted, revoked = diff_missions(before, after)
        assert granted == set()
        assert revoked == set()

    def test_full_seven_keys_all_granted(self):
        """The « grant everything in one POST » case : every key
        flips False -> True. ``granted`` carries all 7."""
        before = dict.fromkeys(PERMISSION_VALUES, False)
        after = dict.fromkeys(PERMISSION_VALUES, True)
        granted, revoked = diff_missions(before, after)
        assert granted == set(PERMISSION_VALUES)
        assert revoked == set()

    def test_full_seven_keys_all_revoked(self):
        """The « revoke everything » case (PR Manager is being
        dismissed). ``revoked`` carries all 7."""
        before = dict.fromkeys(PERMISSION_VALUES, True)
        after = dict.fromkeys(PERMISSION_VALUES, False)
        granted, revoked = diff_missions(before, after)
        assert granted == set()
        assert revoked == set(PERMISSION_VALUES)

    def test_diff_is_disjoint(self):
        """A key cannot simultaneously be granted and revoked in a
        single diff (the comparison is point-wise per key). Pin
        the invariant defensively."""
        before = {
            PermissionType.EVENTS.value: True,
            PermissionType.PRESS_RELEASE.value: False,
        }
        after = {
            PermissionType.EVENTS.value: False,
            PermissionType.PRESS_RELEASE.value: True,
        }
        granted, revoked = diff_missions(before, after)
        assert granted.isdisjoint(revoked)

    def test_returns_sets_not_lists(self):
        """The contract is sets — order-independent, dedup-free,
        cheap to intersect. Pin so a future refactor to lists
        (which would silently allow duplicates) is loud."""
        granted, revoked = diff_missions({}, {})
        assert isinstance(granted, set)
        assert isinstance(revoked, set)


class TestResolvePreviousEndpoint:
    """``resolve_previous_endpoint`` picks the « previous » wizard
    step endpoint based on bw_type. Only ``"pr"`` is special-cased;
    everything else falls through to the external-partners step."""

    def test_pr_goes_to_internal_roles(self):
        """PR BWs route to internal-roles for « previous »."""
        assert resolve_previous_endpoint("pr") == "bw_activation.manage_internal_roles"

    @pytest.mark.parametrize(
        "bw_type",
        ["media", "agency", "corporate", "academic", "association", ""],
    )
    def test_non_pr_goes_to_external_partners(self, bw_type):
        """Every other BW type — including the empty string — falls
        through to external-partners. Pin the default branch so a
        refactor that adds another special case is forced to update
        these tests."""
        assert (
            resolve_previous_endpoint(bw_type)
            == "bw_activation.manage_external_partners"
        )

    def test_pr_case_sensitive(self):
        """The branch matches exactly ``"pr"`` lowercase. ``"PR"``
        falls through to external-partners — pin the case-sensitivity
        so a future ``.lower()`` slip is loud."""
        assert (
            resolve_previous_endpoint("PR") == "bw_activation.manage_external_partners"
        )


class TestIsValidAction:
    """``is_valid_action`` whitelists the stage-B6 submit-button
    action keyword. Unknown values fail loudly (the route raises
    ValueError) — pin the whitelist."""

    @pytest.mark.parametrize("action", ["previous", "finish"])
    def test_whitelisted_actions(self, action):
        assert is_valid_action(action) is True

    @pytest.mark.parametrize(
        "action",
        ["next", "cancel", "save", "", "PREVIOUS", "Finish"],
    )
    def test_other_actions_rejected(self, action):
        """Anything not in the whitelist — including casing variants
        of the valid keywords — is rejected. The route turns this
        into a ValueError; a silent default would let the wizard
        skip steps unnoticed."""
        assert is_valid_action(action) is False

    def test_valid_actions_set_shape(self):
        """Pin the whitelist exactly — adding a third action without
        updating the route's redirect dispatch is a silent skip."""
        assert frozenset({"previous", "finish"}) == _VALID_ACTIONS
