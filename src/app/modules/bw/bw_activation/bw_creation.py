# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Utility functions for Business Wall instance creation."""

from __future__ import annotations

from collections.abc import MutableMapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from flask import g

# from app.enums import ProfileEnum
from app.modules.bw.bw_activation.models import BusinessWall, BWStatus

from .config import BW_TYPES

StdDict = dict[str, str | int | float | bool | None]

if TYPE_CHECKING:
    from app.models.auth import User


def create_new_free_bw_record(session: MutableMapping) -> bool:
    if not session.get("bw_activated"):
        return False
    bw_type = session.get("bw_type")
    bw_info = BW_TYPES.get(bw_type, {})
    # this also insure we have a valid BWType
    if not bw_info.get("free"):
        return False

    user = cast("User", g.user)
    org = user.organisation

    now = datetime.now(UTC)

    business_wall = BusinessWall(
        bw_type=bw_type,
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=user.id,
        payer_id=user.id,  # FIXME
        organisation_id=org.id,
        activated_at=now,
        # subscription
        # role_assignments
        # partnerships
    )

    from app.logging import warn

    warn(business_wall)

    # bw_activated True
    # bw_type media
    # bw_type_confirmed True
    # contacts_confirmed True
    # fs_cc set
    # fs_paa 1770888080.965528
    # owner_email eliane@agencetca.info
    # owner_first_name Eliane
    # owner_last_name Kahn
    # owner_phone +33 549179960
    # payer_email eliane@agencetca.info
    # payer_first_name Eliane
    # payer_last_name Kahn
    # payer_phone +33 549179960
    # pricing_value None
    # suggested_bw_type media

    return True
