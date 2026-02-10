# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Repository classes for Business Wall models.

Repositories provide CRUD operations and query methods for models.
"""

from __future__ import annotations

from advanced_alchemy.repository import SQLAlchemySyncRepository

from .business_wall import BusinessWall
from .content import BWContent
from .partnership import Partnership
from .role import RoleAssignment, RolePermission
from .subscription import Subscription


class BusinessWallRepository(SQLAlchemySyncRepository[BusinessWall]):
    """Repository for BusinessWall model."""

    model_type = BusinessWall


class SubscriptionRepository(SQLAlchemySyncRepository[Subscription]):
    """Repository for Subscription model."""

    model_type = Subscription


class RoleAssignmentRepository(SQLAlchemySyncRepository[RoleAssignment]):
    """Repository for RoleAssignment model."""

    model_type = RoleAssignment


class RolePermissionRepository(SQLAlchemySyncRepository[RolePermission]):
    """Repository for RolePermission model."""

    model_type = RolePermission


class PartnershipRepository(SQLAlchemySyncRepository[Partnership]):
    """Repository for Partnership model."""

    model_type = Partnership


class BWContentRepository(SQLAlchemySyncRepository[BWContent]):
    """Repository for BWContent model."""

    model_type = BWContent


__all__ = [
    "BWContentRepository",
    "BusinessWallRepository",
    "PartnershipRepository",
    "RoleAssignmentRepository",
    "RolePermissionRepository",
    "SubscriptionRepository",
]
