# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Repository classes for Business Wall models.

Repositories provide CRUD operations and query methods for models.
"""

from __future__ import annotations

from advanced_alchemy.repository import SQLAlchemySyncRepository

from .business_wall import BusinessWallPoc
from .content import BWContentPoc
from .partnership import PartnershipPoc
from .role import RoleAssignmentPoc, RolePermissionPoc
from .subscription import SubscriptionPoc


class BusinessWallPocRepository(SQLAlchemySyncRepository[BusinessWallPoc]):
    """Repository for BusinessWallPoc model."""

    model_type = BusinessWallPoc


class SubscriptionPocRepository(SQLAlchemySyncRepository[SubscriptionPoc]):
    """Repository for SubscriptionPoc model."""

    model_type = SubscriptionPoc


class RoleAssignmentPocRepository(SQLAlchemySyncRepository[RoleAssignmentPoc]):
    """Repository for RoleAssignmentPoc model."""

    model_type = RoleAssignmentPoc


class RolePermissionPocRepository(SQLAlchemySyncRepository[RolePermissionPoc]):
    """Repository for RolePermissionPoc model."""

    model_type = RolePermissionPoc


class PartnershipPocRepository(SQLAlchemySyncRepository[PartnershipPoc]):
    """Repository for PartnershipPoc model."""

    model_type = PartnershipPoc


class BWContentPocRepository(SQLAlchemySyncRepository[BWContentPoc]):
    """Repository for BWContentPoc model."""

    model_type = BWContentPoc


__all__ = [
    "BWContentPocRepository",
    "BusinessWallPocRepository",
    "PartnershipPocRepository",
    "RoleAssignmentPocRepository",
    "RolePermissionPocRepository",
    "SubscriptionPocRepository",
]
