# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Utility functions for Business Wall instance creation."""

from __future__ import annotations

from collections.abc import MutableMapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from flask import g
from svcs.flask import container

from app.flask.extensions import db
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWallService,
    BWStatus,
    RoleAssignmentService,
    SubscriptionService,
)
from app.modules.bw.bw_activation.models.role import BWRoleType, InvitationStatus
from app.modules.bw.bw_activation.models.subscription import SubscriptionStatus

from .config import BW_TYPES

StdDict = dict[str, str | int | float | bool | datetime | None]


if TYPE_CHECKING:
    from app.models.auth import User


# ── Pure decision helpers ───────────────────────────────────────────
#
# Free / paid BW creation share their entire shape — only the
# `is_free` flag and the « which type is allowed » guard differ. The
# pure helpers below isolate the rules so they can be unit-tested
# without g.user / SVCS / DB.

_TRUTHY_STRINGS: frozenset[Any] = frozenset({True, "true", "on", "yes", "1"})

_PAYER_FIELDS: tuple[str, ...] = (
    "payer_first_name",
    "payer_last_name",
    "payer_service",
    "payer_email",
    "payer_phone",
    "payer_address",
)


def coerce_payer_is_owner(raw: Any) -> bool:
    """Decide if the form's `payer_is_owner` input is truthy.

    Form posts arrive as strings (`"true"`, `"on"`, `"1"`) ; programmatic
    callers pass booleans. Centralise so the « what counts as on »
    rule has a single source of truth — a checkbox that emits `"0"`
    must be treated as False, not as truthy-because-non-empty.
    """
    return raw in _TRUTHY_STRINGS


def extract_payer_fields(
    session: MutableMapping, *, payer_is_owner: bool
) -> dict[str, str]:
    """Pull the payer's contact fields out of `session`.

    When `payer_is_owner` the form skipped them — we emit empty
    strings so the NOT-NULL columns on BW still flush. Otherwise
    we read each session key and stringify ; falsy values (empty
    str, None) become "" so the column never holds None."""
    if payer_is_owner:
        return dict.fromkeys(_PAYER_FIELDS, "")
    return {
        field: (str(session.get(field, "")) if session.get(field) else "")
        for field in _PAYER_FIELDS
    }


def build_bw_payload(
    *,
    bw_type: str,
    user_id: int,
    org_id: int | None,
    activated_at: datetime,
    is_free: bool,
    payer_is_owner: bool,
    payer_fields: dict[str, str],
) -> StdDict:
    """Map form / session inputs onto the `BusinessWallService.create`
    payload. Pure — no DB.

    The two route handlers (`create_new_free_bw_record` and
    `create_new_paid_bw_record`) call this with `is_free=True` /
    `is_free=False` ; every other field is shared, so a divergence
    between the two routes (a typo in one but not the other) shows
    up as a one-line diff here instead of in two parallel call sites.
    """
    return {
        "bw_type": bw_type,
        "status": BWStatus.ACTIVE.value,
        "is_free": is_free,
        "owner_id": int(user_id),
        "payer_id": int(user_id),
        "organisation_id": org_id,
        "activated_at": activated_at,
        "payer_is_owner": payer_is_owner,
        **payer_fields,
    }


def build_subscription_payload(
    *, business_wall_id: Any, started_at: datetime
) -> StdDict:
    """Map a new BW's subscription onto the `SubscriptionService.create`
    payload. Free + paid BWs use identical defaults today (pricing
    `"N/A"`, 0.0 prices) ; if/when paid BWs grow real pricing, the
    diff lands here, not in two parallel callers.
    """
    return {
        "business_wall_id": business_wall_id,
        "status": SubscriptionStatus.ACTIVE.value,
        "started_at": started_at,
        "pricing_field": "N/A",
        "pricing_tier": "N/A",
        "monthly_price": 0.0,
        "annual_price": 0.0,
    }


def build_owner_role_payload(
    *, business_wall_id: Any, user_id: int, accepted_at: datetime
) -> StdDict:
    """Map the owner-role assignment onto the
    `RoleAssignmentService.create` payload. The user creating the BW
    auto-accepts the OWNER role at creation time."""
    return {
        "business_wall_id": business_wall_id,
        "user_id": user_id,
        "role_type": BWRoleType.BW_OWNER.value,
        "invitation_status": InvitationStatus.ACCEPTED.value,
        "accepted_at": accepted_at,
    }


def select_bw_type(session: MutableMapping, *, want_free: bool) -> str | None:
    """Validate session preconditions for BW creation and return the
    chosen `bw_type` — or None if any precondition fails.

    Three rules :

    1. `bw_activated` must be truthy : the user actually clicked OK
       on the activation form (no direct call to the route).
    2. `bw_type` must resolve to a known entry in `BW_TYPES` — guard
       against typos / tampered session.
    3. The entry's `free` flag must match `want_free` — the « free »
       and « paid » routes don't accept each other's types.
    """
    if not session.get("bw_activated"):
        return None
    bw_type = session.get("bw_type")
    if not bw_type:
        return None
    bw_info = BW_TYPES.get(bw_type, {})
    if not bw_info:
        return None
    if bool(bw_info.get("free")) != want_free:
        return None
    return bw_type


# ── Imperative shell ────────────────────────────────────────────────


def _create_required_organisation(user: User, bw_info: dict[str, Any], bw_type: str):
    """Create a minimal Organisation (required to create a BW)

    Should not happen very often, but User can register without create an Organisation"""

    org_name = cast(str, bw_info.get("name", f"Org for BW {bw_type}"))
    org = Organisation(name=org_name)
    db.session.add(org)
    # Associate user with the new organisation
    user.organisation = org
    db.session.flush()


def _create_bw_record(session: MutableMapping, *, want_free: bool) -> bool:
    """Shared shell for the free + paid creation paths. Returns True
    on success, False if a precondition fails."""
    bw_type = select_bw_type(session, want_free=want_free)
    if bw_type is None:
        return False

    bw_info = BW_TYPES.get(bw_type, {})
    user = cast("User", g.user)
    org = user.organisation
    # Edge case: create minimal organisation if user doesn't have one
    if org is None:
        _create_required_organisation(user, bw_info, bw_type)
        org = user.organisation

    now = datetime.now(UTC)
    bw_service = container.get(BusinessWallService)
    subscription_service = container.get(SubscriptionService)
    role_service = container.get(RoleAssignmentService)

    payer_is_owner = coerce_payer_is_owner(session.get("payer_is_owner", False))
    payer_fields = extract_payer_fields(session, payer_is_owner=payer_is_owner)

    business_wall = bw_service.create(
        build_bw_payload(
            bw_type=bw_type,
            user_id=int(user.id),
            org_id=int(org.id) if org and org.id else None,
            activated_at=now,
            is_free=want_free,
            payer_is_owner=payer_is_owner,
            payer_fields=payer_fields,
        ),
        auto_commit=False,
    )

    subscription_service.create(
        build_subscription_payload(business_wall_id=business_wall.id, started_at=now),
        auto_commit=False,
    )

    role_service.create(
        build_owner_role_payload(
            business_wall_id=business_wall.id, user_id=user.id, accepted_at=now
        ),
        auto_commit=False,
    )

    if org:
        org.bw_active = business_wall.bw_type
        org.bw_id = business_wall.id

    # commit do not happen in the utility fonction
    return True


def create_new_free_bw_record(session: MutableMapping) -> bool:
    """Create a new free Business Wall record .

    Args:
        session: request session dictionary.

    Returns:
        bool: creation success.
    """
    return _create_bw_record(session, want_free=True)


def create_new_paid_bw_record(session: MutableMapping) -> bool:
    """Create a new paid Business Wall record .

    Args:
        session: request session dictionary.

    Returns:
        bool: creation success.
    """
    return _create_bw_record(session, want_free=False)
