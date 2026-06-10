# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure decision helpers in `bw_activation/bw_creation`.

`create_new_free_bw_record` and `create_new_paid_bw_record` were two
near-identical 100-line walls of session reads, container lookups,
type coercions and three `service.create({...})` calls. The pure
pieces are now factored out :

* `coerce_payer_is_owner` — the truthy-set check
* `extract_payer_fields` — empty for the owner branch, session reads
  for the third-party branch
* `select_bw_type` — preconditions + free/paid routing
* `build_bw_payload`, `build_subscription_payload`,
  `build_owner_role_payload` — the three service-call dicts

Pinning every default and every field route at a_unit tier means a
typo in one of these payloads (e.g. dropping `is_free`, swapping
owner_id and payer_id) fails in milliseconds instead of waiting for
b_integration. Guard tests already pin the early-return shape
(`test_bw_creation_helpers.py`) ; this file complements them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.modules.bw.bw_activation.bw_creation import (
    build_bw_payload,
    build_owner_role_payload,
    build_subscription_payload,
    coerce_payer_is_owner,
    extract_payer_fields,
    select_bw_type,
)
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.models import BWStatus
from app.modules.bw.bw_activation.models.role import (
    BWRoleType,
    InvitationStatus,
)
from app.modules.bw.bw_activation.models.subscription import SubscriptionStatus

# ---------------------------------------------------------------------------
# coerce_payer_is_owner — form-string vs bool truthy mapping
# ---------------------------------------------------------------------------


class TestCoercePayerIsOwner:
    @pytest.mark.parametrize("raw", [True, "true", "on", "yes", "1"])
    def test_truthy_form_values(self, raw: Any) -> None:
        assert coerce_payer_is_owner(raw) is True

    @pytest.mark.parametrize(
        "raw", [False, "false", "off", "no", "0", "", None, 0, "FALSE"]
    )
    def test_falsy_values(self, raw: Any) -> None:
        """Crucially `"0"` and `""` are falsy — a checkbox that emits
        `"0"` for unchecked must NOT be treated as truthy-because-non-empty.
        Pin so a refactor that swaps to plain `bool(raw)` doesn't
        flip the meaning of an unchecked box."""
        assert coerce_payer_is_owner(raw) is False

    def test_case_sensitive_to_canonical_strings(self) -> None:
        """`"True"` (capitalised) is NOT recognised — the truthy set
        is exactly the lowercase form-encoded values. Pin so a refactor
        that adds `.lower()` is deliberate."""
        assert coerce_payer_is_owner("True") is False


# ---------------------------------------------------------------------------
# extract_payer_fields — owner branch vs third-party branch
# ---------------------------------------------------------------------------


_ALL_PAYER_KEYS = (
    "payer_first_name",
    "payer_last_name",
    "payer_service",
    "payer_email",
    "payer_phone",
    "payer_address",
)


class TestExtractPayerFields:
    def test_owner_branch_yields_empty_strings(self) -> None:
        """When the form said `payer_is_owner=True`, the third-party
        contact fields aren't collected — emit empty strings so the
        NOT-NULL columns on BW still flush."""
        session = {
            # Even if the session leaked stale values, the owner branch
            # should discard them.
            "payer_first_name": "ghost",
            "payer_email": "ghost@example.com",
        }
        result = extract_payer_fields(session, payer_is_owner=True)
        assert result == dict.fromkeys(_ALL_PAYER_KEYS, "")

    def test_third_party_branch_reads_each_field(self) -> None:
        session = {
            "payer_first_name": "Alice",
            "payer_last_name": "Martin",
            "payer_service": "Comptabilité",
            "payer_email": "alice@example.com",
            "payer_phone": "+33-1-23-45-67-89",
            "payer_address": "12 rue de la République",
        }
        result = extract_payer_fields(session, payer_is_owner=False)
        assert result == session

    def test_third_party_branch_defaults_missing_to_empty(self) -> None:
        """Form may omit some fields ; defaults to "" rather than
        propagating None into a NOT-NULL string column."""
        session = {"payer_first_name": "Alice"}
        result = extract_payer_fields(session, payer_is_owner=False)
        assert result["payer_first_name"] == "Alice"
        assert result["payer_email"] == ""
        assert result["payer_address"] == ""

    def test_third_party_branch_coerces_non_string_to_str(self) -> None:
        """Form fields are always strings ; some test fixtures pass
        ints (postcode, phone w/o spaces). Pin the coercion so column
        types stay clean."""
        session = {"payer_phone": 33123456789}
        result = extract_payer_fields(session, payer_is_owner=False)
        assert result["payer_phone"] == "33123456789"

    def test_returns_all_six_keys_regardless_of_branch(self) -> None:
        """Pin the column shape — the BW row needs all six payer_*
        columns populated, owner branch or not."""
        owner = extract_payer_fields({}, payer_is_owner=True)
        third = extract_payer_fields({}, payer_is_owner=False)
        assert set(owner.keys()) == set(_ALL_PAYER_KEYS)
        assert set(third.keys()) == set(_ALL_PAYER_KEYS)


# ---------------------------------------------------------------------------
# select_bw_type — preconditions + free/paid routing
# ---------------------------------------------------------------------------


def _first_free_type() -> str:
    return next(t for t, info in BW_TYPES.items() if info.get("free"))


def _first_paid_type() -> str:
    return next(t for t, info in BW_TYPES.items() if not info.get("free"))


class TestSelectBwType:
    def test_missing_bw_activated_returns_none(self) -> None:
        """Session arriving without the activation flag : user
        somehow hit the route without clicking OK. Don't create the BW."""
        session = {"bw_type": _first_free_type()}
        assert select_bw_type(session, want_free=True) is None

    def test_missing_bw_type_returns_none(self) -> None:
        session = {"bw_activated": True}
        assert select_bw_type(session, want_free=True) is None

    def test_unknown_bw_type_returns_none(self) -> None:
        """Tampered or stale session value — the bw_type isn't in
        the registry. Refuse rather than silently fail later."""
        session = {"bw_activated": True, "bw_type": "non_existent_type"}
        assert select_bw_type(session, want_free=True) is None

    def test_paid_type_rejected_on_free_route(self) -> None:
        """A user requesting a paid BW from the free route is a sign
        of either a tampered session or a routing bug. Refuse so the
        free path can't accidentally provision a paid type."""
        paid = _first_paid_type()
        session = {"bw_activated": True, "bw_type": paid}
        assert select_bw_type(session, want_free=True) is None

    def test_free_type_rejected_on_paid_route(self) -> None:
        free = _first_free_type()
        session = {"bw_activated": True, "bw_type": free}
        assert select_bw_type(session, want_free=False) is None

    def test_valid_free_type_returns_type_name(self) -> None:
        free = _first_free_type()
        session = {"bw_activated": True, "bw_type": free}
        assert select_bw_type(session, want_free=True) == free

    def test_valid_paid_type_returns_type_name(self) -> None:
        paid = _first_paid_type()
        session = {"bw_activated": True, "bw_type": paid}
        assert select_bw_type(session, want_free=False) == paid


# ---------------------------------------------------------------------------
# build_bw_payload — `BusinessWallService.create` arg dict
# ---------------------------------------------------------------------------


_FIXED_NOW = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)


class TestBuildBwPayload:
    def _payer_fields(self) -> dict[str, str]:
        return dict.fromkeys(_ALL_PAYER_KEYS, "")

    def test_bw_type_and_status(self) -> None:
        payload = build_bw_payload(
            bw_type="media",
            user_id=7,
            org_id=42,
            activated_at=_FIXED_NOW,
            is_free=True,
            payer_is_owner=True,
            payer_fields=self._payer_fields(),
        )
        assert payload["bw_type"] == "media"
        assert payload["status"] == BWStatus.ACTIVE.value

    def test_is_free_propagates(self) -> None:
        """Pin both shapes — the only behavioural diff between the
        free and paid routes is this flag. A typo here would silently
        provision a free BW from the paid route or vice versa."""
        free_payload = build_bw_payload(
            bw_type="media",
            user_id=7,
            org_id=42,
            activated_at=_FIXED_NOW,
            is_free=True,
            payer_is_owner=True,
            payer_fields=self._payer_fields(),
        )
        paid_payload = build_bw_payload(
            bw_type="media",
            user_id=7,
            org_id=42,
            activated_at=_FIXED_NOW,
            is_free=False,
            payer_is_owner=True,
            payer_fields=self._payer_fields(),
        )
        assert free_payload["is_free"] is True
        assert paid_payload["is_free"] is False

    def test_owner_and_payer_default_to_same_user(self) -> None:
        """Both `owner_id` and `payer_id` default to the activator —
        the « payer is owner » branch covers the case where the user
        is paying for their own BW."""
        payload = build_bw_payload(
            bw_type="media",
            user_id=7,
            org_id=42,
            activated_at=_FIXED_NOW,
            is_free=True,
            payer_is_owner=True,
            payer_fields=self._payer_fields(),
        )
        assert payload["owner_id"] == 7
        assert payload["payer_id"] == 7

    def test_org_id_passed_through(self) -> None:
        payload = build_bw_payload(
            bw_type="media",
            user_id=7,
            org_id=42,
            activated_at=_FIXED_NOW,
            is_free=True,
            payer_is_owner=True,
            payer_fields=self._payer_fields(),
        )
        assert payload["organisation_id"] == 42

    def test_org_id_none_allowed(self) -> None:
        """The orchestrator may pass None when the user has no org
        AND the minimal-org creation failed to assign an id. The
        column is nullable ; pin the pass-through."""
        payload = build_bw_payload(
            bw_type="media",
            user_id=7,
            org_id=None,
            activated_at=_FIXED_NOW,
            is_free=True,
            payer_is_owner=True,
            payer_fields=self._payer_fields(),
        )
        assert payload["organisation_id"] is None

    def test_activated_at_is_routed(self) -> None:
        payload = build_bw_payload(
            bw_type="media",
            user_id=7,
            org_id=42,
            activated_at=_FIXED_NOW,
            is_free=True,
            payer_is_owner=True,
            payer_fields=self._payer_fields(),
        )
        assert payload["activated_at"] == _FIXED_NOW

    def test_payer_fields_spread_into_payload(self) -> None:
        """The 6 payer_* keys land verbatim. Pin so the dict spread
        doesn't accidentally drop one."""
        payer_fields = {
            "payer_first_name": "Alice",
            "payer_last_name": "Martin",
            "payer_service": "Comptabilité",
            "payer_email": "alice@example.com",
            "payer_phone": "+33-1-23-45-67-89",
            "payer_address": "12 rue X",
        }
        payload = build_bw_payload(
            bw_type="media",
            user_id=7,
            org_id=42,
            activated_at=_FIXED_NOW,
            is_free=False,
            payer_is_owner=False,
            payer_fields=payer_fields,
        )
        for k, v in payer_fields.items():
            assert payload[k] == v


# ---------------------------------------------------------------------------
# build_subscription_payload — `SubscriptionService.create` arg dict
# ---------------------------------------------------------------------------


class TestBuildSubscriptionPayload:
    def test_status_defaults_to_active(self) -> None:
        """A newly-activated BW gets an immediately-active
        subscription, even for free types — the « subscription »
        is the audit row, not the billing relationship."""
        payload = build_subscription_payload(
            business_wall_id="bw-123", started_at=_FIXED_NOW
        )
        assert payload["status"] == SubscriptionStatus.ACTIVE.value

    def test_pricing_defaults_to_na_and_zero(self) -> None:
        """Both free and paid routes currently use the same defaults.
        Pin so a future « free is N/A, paid is real pricing » split
        is deliberate, not silent."""
        payload = build_subscription_payload(
            business_wall_id="bw-123", started_at=_FIXED_NOW
        )
        assert payload["pricing_field"] == "N/A"
        assert payload["pricing_tier"] == "N/A"
        assert payload["monthly_price"] == 0.0
        assert payload["annual_price"] == 0.0

    def test_business_wall_id_and_started_at_routed(self) -> None:
        payload = build_subscription_payload(
            business_wall_id="bw-xyz", started_at=_FIXED_NOW
        )
        assert payload["business_wall_id"] == "bw-xyz"
        assert payload["started_at"] == _FIXED_NOW


# ---------------------------------------------------------------------------
# build_owner_role_payload — `RoleAssignmentService.create` arg dict
# ---------------------------------------------------------------------------


class TestBuildOwnerRolePayload:
    def test_role_type_is_bw_owner(self) -> None:
        """The user creating a BW gets the OWNER role — that's the
        security guarantee. Pin so a refactor that swaps to a
        narrower role (e.g. ADMIN) doesn't lose the owner contract."""
        payload = build_owner_role_payload(
            business_wall_id="bw-xyz", user_id=7, accepted_at=_FIXED_NOW
        )
        assert payload["role_type"] == BWRoleType.BW_OWNER.value

    def test_invitation_status_is_accepted(self) -> None:
        """No invitation flow on creation — the owner auto-accepts."""
        payload = build_owner_role_payload(
            business_wall_id="bw-xyz", user_id=7, accepted_at=_FIXED_NOW
        )
        assert payload["invitation_status"] == InvitationStatus.ACCEPTED.value

    def test_accepted_at_routed(self) -> None:
        payload = build_owner_role_payload(
            business_wall_id="bw-xyz", user_id=7, accepted_at=_FIXED_NOW
        )
        assert payload["accepted_at"] == _FIXED_NOW

    def test_business_wall_id_and_user_id_routed(self) -> None:
        payload = build_owner_role_payload(
            business_wall_id="bw-xyz", user_id=42, accepted_at=_FIXED_NOW
        )
        assert payload["business_wall_id"] == "bw-xyz"
        assert payload["user_id"] == 42
