# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure helpers extracted from
`app.modules.bw.bw_activation.routes.rights_policy`.

WHY : the route file mixes Flask request plumbing (form parsing,
flash/redirect, DB commit) with four pure-data operations :
  * `parse_option` — strip a raw form value down to a candidate.
  * `is_valid_option` — membership in the canonical option set.
  * `can_configure_rights_policy` — owner-eligibility predicate on
    BW type.
  * `is_picker_candidate` — predicate matching the SELECT criteria
    of `_get_media_business_walls`.
  * `build_policy_snapshot` — freeze `(option, media_ids)` into the
    JSON payload written onto `BusinessWall.rights_sales_policy`.

Each of these is tested below with plain values and lightweight
stand-ins — no DB, no Flask app context, no mocks. Pin the policy
semantics so a future tweak of the route doesn't silently break
the contract between the form, the DB column, and the
`is_eligible_for_cession` predicate.

Pattern A (functional core / imperative shell) : the 3-line I/O
shell — `request.form.get / db.session.commit / redirect` — stays
covered by the route integration suite.
"""

from __future__ import annotations

import pytest

from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.bw.bw_activation.routes.rights_policy import (
    _VALID_OPTIONS,
    ALLOWED_BW_TYPES,
    PICKER_BW_TYPE,
    VALID_OPTIONS,
    build_policy_snapshot,
    can_configure_rights_policy,
    is_picker_candidate,
    is_valid_option,
    parse_option,
)

# ── parse_option ─────────────────────────────────────────────────────


class TestParseOption:
    """Pure : a single `(raw) -> trimmed_str` step. Pin the empty /
    whitespace / None handling so the route's POST branch stays
    defensive against malformed form input."""

    def test_none_returns_empty_string(self):
        """`request.form.get(...)` returns None for a missing field.
        The helper must coerce to empty string, not propagate None."""
        assert parse_option(None) == ""

    def test_empty_string_returns_empty(self):
        assert parse_option("") == ""

    @pytest.mark.parametrize(
        "raw",
        ["whitelist", "all_subscribed", "blacklist", "none"],
    )
    def test_valid_option_passes_through(self, raw):
        assert parse_option(raw) == raw

    def test_strips_leading_and_trailing_whitespace(self):
        r"""Common HTML form artefact : the browser may submit `\n`
        around a hidden field. Strip aggressively."""
        assert parse_option("  whitelist  ") == "whitelist"
        assert parse_option("\twhitelist\n") == "whitelist"

    def test_internal_whitespace_preserved(self):
        """Only edge whitespace is stripped — internal spacing in a
        bogus value is preserved so `is_valid_option` rejects it."""
        assert parse_option(" not valid ") == "not valid"

    def test_preserves_case(self):
        """`is_valid_option` is case-sensitive ; the trim step must
        not lowercase its input."""
        assert parse_option("Whitelist") == "Whitelist"

    def test_returns_str_type(self):
        """Pin the return type — callers do `if option in SET:`
        which would silently fail on a non-string."""
        assert isinstance(parse_option(None), str)
        assert isinstance(parse_option("x"), str)


# ── is_valid_option ──────────────────────────────────────────────────


class TestIsValidOption:
    """Pure : membership in the canonical 4-option set. Pin the
    closed set so an accidental rename of `whitelist` → `allowed`
    or similar gets caught."""

    @pytest.mark.parametrize(
        "option", ["all_subscribed", "whitelist", "blacklist", "none"]
    )
    def test_known_options_are_valid(self, option):
        assert is_valid_option(option) is True

    @pytest.mark.parametrize(
        "option",
        [
            "",
            "ALL_SUBSCRIBED",  # case sensitive
            "Whitelist",
            "white_list",
            "bogus",
            "subscribed",
            " whitelist",  # leading space, since `parse_option` strips
            "whitelist ",
        ],
    )
    def test_invalid_options_rejected(self, option):
        assert is_valid_option(option) is False

    def test_returns_bool_type(self):
        """Callers branch on the result ; pin so a future refactor
        returning Optional[str] is caught."""
        assert isinstance(is_valid_option("whitelist"), bool)
        assert isinstance(is_valid_option("bogus"), bool)

    def test_valid_options_exact_set(self):
        """Pin the canonical set exactly so a third arm sneaking in
        (or an existing arm being renamed) breaks this test."""
        expected = frozenset(
            {"all_subscribed", "whitelist", "blacklist", "none"}
        )
        assert expected == VALID_OPTIONS

    def test_backward_compat_alias(self):
        """`_VALID_OPTIONS` is the historic name ; keep the alias
        until callers migrate. Pin equality so a refactor of one
        doesn't silently desynchronise."""
        assert _VALID_OPTIONS == VALID_OPTIONS


# ── can_configure_rights_policy ──────────────────────────────────────


class TestCanConfigureRightsPolicy:
    """Pure : eligibility gate for the page itself (the route raises
    NotFound when False). Pin the « media + micro » contract so a
    future addition of agency / pr / academics BWs to the
    rights-policy UI is conscious."""

    @pytest.mark.parametrize("bw_type", ["media", "micro"])
    def test_allowed_bw_types(self, bw_type):
        assert can_configure_rights_policy(bw_type) is True

    @pytest.mark.parametrize(
        "bw_type",
        [
            "agency",
            "pr",
            "academics",
            "leaders_experts",
            "transformers",
            "company",
            "",
            "MEDIA",  # case sensitive
        ],
    )
    def test_disallowed_bw_types(self, bw_type):
        assert can_configure_rights_policy(bw_type) is False

    def test_none_bw_type(self):
        """Defensive : a BW row created from a malformed CSV may
        have `bw_type=None`. The predicate must return False, not
        crash."""
        assert can_configure_rights_policy(None) is False

    def test_returns_bool_type(self):
        assert isinstance(can_configure_rights_policy("media"), bool)
        assert isinstance(can_configure_rights_policy("agency"), bool)

    def test_allowed_set_pinned(self):
        """Pin the canonical set exactly. Bug #0112 added `micro` ;
        a future rollback of that bug-fix would be caught here."""
        assert ALLOWED_BW_TYPES == ("media", "micro")


# ── is_picker_candidate ──────────────────────────────────────────────


class TestIsPickerCandidate:
    """Pure : mirrors the WHERE clause of `_get_media_business_walls`
    so the (bw_type == 'media' AND status == 'active') criteria
    are unit-testable. Pin the contract so a future broadening (e.g.
    let `micro` BWs appear in the picker too) is conscious."""

    def test_active_media_is_candidate(self):
        assert is_picker_candidate("media", BWStatus.ACTIVE.value) is True

    @pytest.mark.parametrize(
        "status",
        [
            BWStatus.DRAFT.value,
            BWStatus.SUSPENDED.value,
            BWStatus.CANCELLED.value,
        ],
    )
    def test_non_active_media_rejected(self, status):
        """A draft / suspended / cancelled `media` BW must NOT
        appear in the picker — pin so a future « show suspended too »
        regression is caught."""
        assert is_picker_candidate("media", status) is False

    @pytest.mark.parametrize(
        "bw_type",
        ["micro", "agency", "pr", "company", "academics", ""],
    )
    def test_non_media_rejected(self, bw_type):
        """Even an `active` non-media BW is excluded — the picker
        lists publishers only. Pin so a future « add micro to the
        picker » is conscious."""
        assert is_picker_candidate(bw_type, BWStatus.ACTIVE.value) is False

    def test_none_bw_type_rejected(self):
        assert is_picker_candidate(None, BWStatus.ACTIVE.value) is False

    def test_none_status_rejected(self):
        assert is_picker_candidate("media", None) is False

    def test_both_none_rejected(self):
        assert is_picker_candidate(None, None) is False

    def test_returns_bool_type(self):
        assert isinstance(
            is_picker_candidate("media", BWStatus.ACTIVE.value), bool
        )

    def test_picker_bw_type_constant(self):
        """Pin the canonical picker type so the SELECT statement
        and the predicate stay in sync."""
        assert PICKER_BW_TYPE == "media"

    def test_case_sensitive_bw_type(self):
        """Pin case-sensitivity — `MEDIA` is rejected."""
        assert is_picker_candidate("MEDIA", BWStatus.ACTIVE.value) is False

    def test_case_sensitive_status(self):
        assert is_picker_candidate("media", "ACTIVE") is False


# ── build_policy_snapshot ────────────────────────────────────────────


class TestBuildPolicySnapshot:
    """Pure : `(option, media_ids) -> dict` for the DB write.

    The shape is consumed by `rights_policy.get_policy` on the way
    out — pin so a divergence between the writer (route) and the
    reader (`get_policy`) breaks here, not at runtime in front of
    a customer."""

    def test_basic_shape(self):
        snapshot = build_policy_snapshot("whitelist", ["bw-1", "bw-2"])
        assert snapshot == {
            "option": "whitelist",
            "media_ids": ["bw-1", "bw-2"],
        }

    @pytest.mark.parametrize(
        "option", ["all_subscribed", "whitelist", "blacklist", "none"]
    )
    def test_option_pass_through(self, option):
        snapshot = build_policy_snapshot(option, [])
        assert snapshot["option"] == option

    def test_empty_media_ids(self):
        """`option=none` or `option=all_subscribed` ignore media_ids
        downstream — the snapshot still carries an empty list (not
        None) for shape consistency."""
        snapshot = build_policy_snapshot("none", [])
        assert snapshot["media_ids"] == []
        assert isinstance(snapshot["media_ids"], list)

    def test_media_ids_pass_through_unchanged(self):
        """The route passes through whatever `request.form.getlist`
        returns — coercion to string happens on the READ side in
        `get_policy`. Pin so the writer doesn't acquire its own
        coercion (would split the responsibility)."""
        ids = ["uuid-1", "uuid-2", "uuid-3"]
        snapshot = build_policy_snapshot("whitelist", ids)
        assert snapshot["media_ids"] == ids

    def test_keys_exact(self):
        """Pin the exact keys — no extra fields. A future addition
        (e.g. `version`) MUST be a conscious schema change."""
        snapshot = build_policy_snapshot("whitelist", [])
        assert set(snapshot.keys()) == {"option", "media_ids"}

    def test_invalid_option_still_serialised(self):
        """The route's I/O shell calls `is_valid_option` BEFORE
        building the snapshot. The builder itself is content-
        agnostic — pin that contract so the builder stays the
        single source of shape, not a second validator."""
        snapshot = build_policy_snapshot("bogus", [])
        assert snapshot == {"option": "bogus", "media_ids": []}

    def test_does_not_mutate_input_list(self):
        """The route passes `request.form.getlist` directly — the
        builder must NOT mutate the caller's list."""
        ids = ["a", "b"]
        original = list(ids)
        build_policy_snapshot("whitelist", ids)
        assert ids == original

    def test_returns_dict_type(self):
        snapshot = build_policy_snapshot("none", [])
        assert isinstance(snapshot, dict)


# ── end-to-end pure-pipeline integration ────────────────────────────


class TestPureFormPipeline:
    """Integration over the pure layer only : simulate the « POST
    handler » sequence with a `request.form`-like dict and verify
    the resulting payload that *would* be written to the DB.

    No Flask, no DB — just the pure functions composed in the same
    order the route uses them. Pin the integration so a future
    refactor that moves the validation step around is conscious."""

    def _process(
        self, raw_option: str | None, media_ids: list[str]
    ) -> dict | None:
        """Run the pure pipeline ; return the snapshot OR None if
        the input would be rejected (matches the route's redirect-
        with-flash branch)."""
        option = parse_option(raw_option)
        if not is_valid_option(option):
            return None
        return build_policy_snapshot(option, media_ids)

    def test_happy_path_whitelist(self):
        result = self._process("whitelist", ["bw-1", "bw-2"])
        assert result == {
            "option": "whitelist",
            "media_ids": ["bw-1", "bw-2"],
        }

    def test_happy_path_all_subscribed(self):
        """`all_subscribed` with no media_ids is the « pre-MVP
        default » — the snapshot still carries an empty list."""
        result = self._process("all_subscribed", [])
        assert result == {"option": "all_subscribed", "media_ids": []}

    def test_invalid_option_rejected(self):
        """`option=bogus` → `is_valid_option` returns False → the
        route flashes an error and redirects. The pure pipeline
        signals this by returning None."""
        assert self._process("bogus", []) is None

    def test_missing_option_rejected(self):
        """`request.form.get('option')` returns None when the form
        field is absent. Pipeline returns None → route flashes."""
        assert self._process(None, []) is None

    def test_whitespace_only_option_rejected(self):
        """A whitespace-only field strips down to empty, which is
        not in the canonical set."""
        assert self._process("   ", []) is None

    def test_whitespace_around_valid_option_accepted(self):
        """`parse_option` strips ; downstream sees the canonical
        value. Pin the user-friendly behaviour."""
        result = self._process("  whitelist  ", ["bw-1"])
        assert result is not None
        assert result["option"] == "whitelist"

    @pytest.mark.parametrize(
        "option", ["all_subscribed", "whitelist", "blacklist", "none"]
    )
    def test_all_canonical_options_round_trip(self, option):
        """Every valid option survives the pipeline unchanged."""
        result = self._process(option, ["bw-1"])
        assert result is not None
        assert result["option"] == option
