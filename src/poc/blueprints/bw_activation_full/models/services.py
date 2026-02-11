# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Service classes for Business Wall models.

Services provide high-level business logic operations using repositories.
"""

from __future__ import annotations

from advanced_alchemy.extensions.flask import FlaskServiceMixin
from advanced_alchemy.service import SQLAlchemySyncRepositoryService

from .business_wall import BusinessWallPoc
from .content import BWContentPoc
from .partnership import PartnershipPoc
from .repositories import (
    BusinessWallPocRepository,
    BWContentPocRepository,
    PartnershipPocRepository,
    RoleAssignmentPocRepository,
    RolePermissionPocRepository,
    SubscriptionPocRepository,
)
from .role import RoleAssignmentPoc, RolePermissionPoc
from .subscription import SubscriptionPoc


class BusinessWallPocService(
    FlaskServiceMixin, SQLAlchemySyncRepositoryService[BusinessWallPoc]
):
    """Service for BusinessWallPoc operations.

    Provides high-level business logic for managing Business Walls.
    """

    repository_type = BusinessWallPocRepository


class SubscriptionPocService(
    FlaskServiceMixin, SQLAlchemySyncRepositoryService[SubscriptionPoc]
):
    """Service for SubscriptionPoc operations.

    Handles subscription creation, updates, and payment tracking.
    """

    repository_type = SubscriptionPocRepository


class RoleAssignmentPocService(
    FlaskServiceMixin, SQLAlchemySyncRepositoryService[RoleAssignmentPoc]
):
    """Service for RoleAssignmentPoc operations.

    Manages role assignments and invitation workflow.
    """

    repository_type = RoleAssignmentPocRepository


class RolePermissionPocService(
    FlaskServiceMixin, SQLAlchemySyncRepositoryService[RolePermissionPoc]
):
    """Service for RolePermissionPoc operations.

    Manages granular permissions for PR Managers.
    """

    repository_type = RolePermissionPocRepository


class PartnershipPocService(
    FlaskServiceMixin, SQLAlchemySyncRepositoryService[PartnershipPoc]
):
    """Service for PartnershipPoc operations.

    Manages PR Agency partnerships and invitation workflow.
    """

    repository_type = PartnershipPocRepository


class BWContentPocService(
    FlaskServiceMixin, SQLAlchemySyncRepositoryService[BWContentPoc]
):
    """Service for BWContentPoc operations.

    Manages Business Wall content and configuration.
    """

    repository_type = BWContentPocRepository


__all__ = [
    "BWContentPocService",
    "BusinessWallPocService",
    "PartnershipPocService",
    "RoleAssignmentPocService",
    "RolePermissionPocService",
    "SubscriptionPocService",
]
