# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall invitation management utils."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.bw.bw_activation.models import BusinessWall


def change_bwmi_emails(business_wall: BusinessWall, raw_mails: str) -> None:
    """Update BWMi invitations based on email list."""
    pass


def change_bwpri_emails(business_wall: BusinessWall, raw_mails: str) -> None:
    """Update BWPRi invitations based on email list."""
    pass
