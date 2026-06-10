# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the early BW activation stages (stage1 / stage2).

The route handlers themselves are Flask-+-DB-coupled and live in the
e2e tier (`tests/c_e2e/modules/bw/test_stage1.py`,
`tests/c_e2e/modules/bw/test_bw_routes.py`). The route bodies, however,
are thin imperative shells around a small number of pure decisions:

  - which BW types are accepted by `select_subscription`
    (`is_valid_bw_type`),
  - how to drop CANCELLED BWs before the index() auto-pick
    (`filter_active_manageable`),
  - how to flatten a stage-2 contact form into the eight session keys
    the route writes (`parse_contacts_form`), including the
    « same_as_owner » duplication rule,
  - which endpoint stage-2 redirects to once contacts are stored —
    free types → activate_free_page, paid types → pricing_page
    (`post_contacts_redirect_endpoint`).

These pure helpers were lifted out (Pattern A) so the dispatch
contract can be pinned without a Flask app context, a DB session, or
any user / BusinessWall ORM instance. We exercise them here with
plain dicts and a stand-in BW dataclass — pure inputs, pure outputs,
no test doubles needed.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.models.business_wall import BWStatus, BWType
from app.modules.bw.bw_activation.routes.stage1 import (
    filter_active_manageable,
    is_valid_bw_type,
)
from app.modules.bw.bw_activation.routes.stage2 import (
    parse_contacts_form,
    post_contacts_redirect_endpoint,
)


# Stand-in BW row — duck-typed to the single attribute
# `filter_active_manageable` reads.
@dataclass
class _BwRow:
    status: str


# ---------------------------------------------------------------------------
# stage1 — pure helpers
# ---------------------------------------------------------------------------


class TestIsValidBwType:
    """Pin the validator the `select_subscription` route uses to
    decide whether to accept the URL-supplied `bw_type` or redirect
    back to `confirm_subscription`.

    Each member of `BWType` must round-trip through `BW_TYPES`,
    otherwise activation for that subscription is silently broken.
    Conversely, anything else (typos, legacy values, empty string,
    case variants) must be rejected.
    """

    @pytest.mark.parametrize("bw_type", [member.value for member in BWType])
    def test_every_bw_type_member_is_valid(self, bw_type: str) -> None:
        assert is_valid_bw_type(bw_type) is True

    @pytest.mark.parametrize(
        "bad_value",
        [
            "",
            "MEDIA",  # case-sensitive — uppercase is not the storage form
            "Media",
            "not-a-type",
            "press-union",  # legacy-looking key
            "free",
        ],
    )
    def test_unknown_values_are_rejected(self, bad_value: str) -> None:
        assert is_valid_bw_type(bad_value) is False

    def test_validator_and_config_agree_on_set(self) -> None:
        """The validator must accept exactly the keys present in
        `BW_TYPES` — otherwise `select_subscription` and the
        downstream `BW_TYPES[bw_type]["free"]` lookup would drift."""
        for key in BW_TYPES:
            assert is_valid_bw_type(key) is True


class TestFilterActiveManageable:
    """Pin the « ignore CANCELLED BWs » rule that drives the index()
    auto-pick.

    A user with several historical CANCELLED BWs plus a single
    ACTIVE one must land on the dashboard (length == 1 path), not on
    the /select-bw page. The filter is what makes that happen.
    """

    def test_empty_list_returns_empty_list(self) -> None:
        assert filter_active_manageable([]) == []

    def test_drops_cancelled(self) -> None:
        cancelled = _BwRow(status=BWStatus.CANCELLED.value)
        active = _BwRow(status=BWStatus.ACTIVE.value)
        kept = filter_active_manageable([cancelled, active])
        assert kept == [active]

    @pytest.mark.parametrize(
        "status",
        [
            BWStatus.DRAFT.value,
            BWStatus.ACTIVE.value,
            BWStatus.SUSPENDED.value,
        ],
    )
    def test_non_cancelled_statuses_are_kept(self, status: str) -> None:
        """DRAFT / ACTIVE / SUSPENDED must all reach the auto-pick —
        a user mid-reconfiguration (DRAFT) or temporarily-suspended
        should still land on their BW dashboard."""
        row = _BwRow(status=status)
        assert filter_active_manageable([row]) == [row]

    def test_only_cancelled_yields_empty(self) -> None:
        rows = [_BwRow(status=BWStatus.CANCELLED.value) for _ in range(3)]
        assert filter_active_manageable(rows) == []

    def test_preserves_relative_order(self) -> None:
        """The route uses the list length and `[0]` — order must be
        stable so the auto-pick is deterministic across requests."""
        first = _BwRow(status=BWStatus.ACTIVE.value)
        cancelled = _BwRow(status=BWStatus.CANCELLED.value)
        second = _BwRow(status=BWStatus.DRAFT.value)
        kept = filter_active_manageable([first, cancelled, second])
        assert kept == [first, second]


# ---------------------------------------------------------------------------
# stage2 — pure helpers
# ---------------------------------------------------------------------------


# A complete owner+payer form payload, used as the baseline by most
# stage-2 parser tests.
_FULL_FORM: dict[str, str] = {
    "owner_first_name": "Alice",
    "owner_last_name": "Martin",
    "owner_email": "alice@example.org",
    "owner_phone": "+33 1 23 45 67 89",
    "payer_first_name": "Bob",
    "payer_last_name": "Durand",
    "payer_email": "bob@example.org",
    "payer_phone": "+33 9 87 65 43 21",
}


class TestParseContactsFormDistinctPayer:
    """Pin the « distinct owner / payer » branch.

    When the form does NOT contain `same_as_owner=on`, every owner_*
    and payer_* field must round-trip independently. This is the
    branch the e2e `test_submit_contacts_different_payer` test
    exercises end-to-end — here we cover the parser alone so the
    contract holds even when the route shell is later refactored.
    """

    def test_owner_fields_round_trip(self) -> None:
        parsed = parse_contacts_form(_FULL_FORM)
        assert parsed["owner_first_name"] == "Alice"
        assert parsed["owner_last_name"] == "Martin"
        assert parsed["owner_email"] == "alice@example.org"
        assert parsed["owner_phone"] == "+33 1 23 45 67 89"

    def test_payer_fields_round_trip_when_distinct(self) -> None:
        parsed = parse_contacts_form(_FULL_FORM)
        assert parsed["payer_first_name"] == "Bob"
        assert parsed["payer_last_name"] == "Durand"
        assert parsed["payer_email"] == "bob@example.org"
        assert parsed["payer_phone"] == "+33 9 87 65 43 21"

    def test_returns_exactly_eight_keys(self) -> None:
        """The parser must write 8 session keys: 4 owner + 4 payer.
        Adding a key here silently grows the session schema."""
        parsed = parse_contacts_form(_FULL_FORM)
        assert set(parsed) == {
            "owner_first_name",
            "owner_last_name",
            "owner_email",
            "owner_phone",
            "payer_first_name",
            "payer_last_name",
            "payer_email",
            "payer_phone",
        }


class TestParseContactsFormSameAsOwner:
    """Pin the « same_as_owner » duplication rule.

    When the checkbox is on, the route copies owner_* over payer_*
    regardless of any payer_* values submitted. That contract used
    to live inside the route body — this test pins it on the pure
    parser.
    """

    def test_same_as_owner_on_copies_owner_to_payer(self) -> None:
        form: dict[str, str] = {
            **_FULL_FORM,
            "same_as_owner": "on",
        }
        parsed = parse_contacts_form(form)
        assert parsed["payer_first_name"] == "Alice"
        assert parsed["payer_last_name"] == "Martin"
        assert parsed["payer_email"] == "alice@example.org"
        assert parsed["payer_phone"] == "+33 1 23 45 67 89"

    def test_same_as_owner_on_ignores_submitted_payer_fields(self) -> None:
        """Even if the form ships payer_* values (e.g. the user
        filled them then ticked the checkbox), the checkbox wins.
        Otherwise the « same payer » UX guarantee leaks."""
        form: dict[str, str] = {
            "owner_first_name": "Alice",
            "owner_last_name": "Martin",
            "owner_email": "alice@example.org",
            "owner_phone": "+33 1 23 45 67 89",
            "payer_first_name": "STALE",
            "payer_last_name": "STALE",
            "payer_email": "stale@example.org",
            "payer_phone": "00000",
            "same_as_owner": "on",
        }
        parsed = parse_contacts_form(form)
        assert parsed["payer_first_name"] == "Alice"
        assert parsed["payer_email"] == "alice@example.org"

    @pytest.mark.parametrize(
        "checkbox_value",
        ["", "off", "true", "1", "yes", "On", "ON"],
    )
    def test_only_literal_on_triggers_duplication(
        self, checkbox_value: str
    ) -> None:
        """HTML checkboxes ship the literal string « on » when ticked
        (per Flask + browser behaviour). Anything else must be
        treated as « distinct payer » — otherwise a forged « true »
        or a localized « ON » would silently impersonate the owner."""
        form: dict[str, str] = {**_FULL_FORM, "same_as_owner": checkbox_value}
        parsed = parse_contacts_form(form)
        assert parsed["payer_first_name"] == "Bob"
        assert parsed["payer_email"] == "bob@example.org"

    def test_same_as_owner_missing_treated_as_off(self) -> None:
        """When the checkbox key is absent from the form (Flask /
        WTForms idiom for « not ticked »), the distinct-payer branch
        must fire."""
        parsed = parse_contacts_form(_FULL_FORM)
        assert parsed["payer_first_name"] == "Bob"


class TestParseContactsFormMissingFields:
    """Pin behaviour for partial / empty form submissions.

    `request.form.get(key)` returns None for missing keys; the parser
    must propagate that without raising so the session keeps existing
    semantics (route would just write None).
    """

    def test_empty_form_returns_all_none(self) -> None:
        parsed = parse_contacts_form({})
        for value in parsed.values():
            assert value is None

    def test_missing_payer_keys_become_none_when_distinct(self) -> None:
        form: dict[str, str] = {
            "owner_first_name": "Alice",
            "owner_last_name": "Martin",
            "owner_email": "alice@example.org",
            "owner_phone": "+33 1 23 45 67 89",
        }
        parsed = parse_contacts_form(form)
        assert parsed["owner_first_name"] == "Alice"
        assert parsed["payer_first_name"] is None
        assert parsed["payer_email"] is None

    def test_same_as_owner_propagates_none_owner_to_payer(self) -> None:
        """Edge case: owner_* itself is missing but same_as_owner is
        on. The parser must duplicate None → payer_* and not raise."""
        form: dict[str, str | None] = {"same_as_owner": "on"}
        parsed = parse_contacts_form(form)
        assert parsed["owner_first_name"] is None
        assert parsed["payer_first_name"] is None


class TestPostContactsRedirectEndpoint:
    """Pin the « free → activate / paid → pricing » dispatch.

    The stage-2 handler chooses the next stage purely from the
    `BW_TYPES[bw_type]["free"]` flag. Adding a new BW type without
    setting `free` would `KeyError` here at PR time — much better
    than a 500 in production.
    """

    @pytest.mark.parametrize(
        "bw_type",
        [
            BWType.MEDIA.value,
            BWType.MICRO.value,
            BWType.CORPORATE_MEDIA.value,
            BWType.UNION.value,
            BWType.ACADEMICS.value,
        ],
    )
    def test_free_types_redirect_to_activate_free_page(self, bw_type: str) -> None:
        assert (
            post_contacts_redirect_endpoint(bw_type)
            == "bw_activation.activate_free_page"
        )

    @pytest.mark.parametrize(
        "bw_type",
        [
            BWType.PR.value,
            BWType.LEADERS_EXPERTS.value,
            BWType.TRANSFORMERS.value,
        ],
    )
    def test_paid_types_redirect_to_pricing_page(self, bw_type: str) -> None:
        assert (
            post_contacts_redirect_endpoint(bw_type) == "bw_activation.pricing_page"
        )

    def test_every_configured_type_is_classified(self) -> None:
        """Every key present in `BW_TYPES` must be routable —
        otherwise a user who picks a configured-but-unclassified
        type lands on a 500 mid-activation."""
        for bw_type in BW_TYPES:
            endpoint = post_contacts_redirect_endpoint(bw_type)
            assert endpoint in {
                "bw_activation.activate_free_page",
                "bw_activation.pricing_page",
            }

    def test_unknown_type_raises_key_error(self) -> None:
        """The route only calls this helper after `select_subscription`
        has validated the type, so a KeyError is the right loud
        failure mode — better than a silent wrong-page redirect."""
        with pytest.raises(KeyError):
            post_contacts_redirect_endpoint("not-a-type")
