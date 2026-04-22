# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Helpers for counting BW customers (PR agency client BWs)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select

from app.flask.extensions import db
from app.modules.bw.bw_activation.models import BusinessWall, Partnership
from app.modules.bw.bw_activation.models.business_wall import BWType

_ACTIVE_PARTNERSHIP_STATUSES = {"accepted", "active"}


def count_pr_bw_customers(bw_id: str | UUID) -> int:
    """Return the number of client BWs that have the given PR BW as partner.

    Counts partnerships with status "accepted" or "active". If the BW does
    not exist or is not of type "PR", returns 0.

    Args:
        bw_id: The BusinessWall id (UUID or string).

    Returns:
        Number of clients.
    """
    try:
        bw_uuid = UUID(str(bw_id))
    except ValueError:
        return 0

    bw = (
        db.session.execute(select(BusinessWall).where(BusinessWall.id == bw_uuid))
        .scalars()
        .one_or_none()
    )

    if bw is None or bw.bw_type != BWType.PR.value:
        return 0

    stmt = (
        select(func.count())
        .select_from(Partnership)
        .where(
            Partnership.partner_bw_id == str(bw.id),
            Partnership.status.in_(_ACTIVE_PARTNERSHIP_STATUSES),
        )
    )
    result = db.session.execute(stmt).scalar_one()
    return result
