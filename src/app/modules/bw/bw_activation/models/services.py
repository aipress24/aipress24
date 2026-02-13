# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Service classes for Business Wall models.

Services provide high-level business logic operations using repositories.
"""

from __future__ import annotations

from advanced_alchemy.extensions.flask import FlaskServiceMixin
from advanced_alchemy.service import SQLAlchemySyncRepositoryService
from flask_super.decorators import service

from .business_wall import BusinessWall
from .content import BWContent
from .partnership import Partnership
from .repositories import (
    BusinessWallRepository,
    BWContentRepository,
    PartnershipRepository,
    RoleAssignmentRepository,
    RolePermissionRepository,
    SubscriptionRepository,
)
from .role import RoleAssignment, RolePermission
from .subscription import Subscription


@service
class BusinessWallService(
    FlaskServiceMixin, SQLAlchemySyncRepositoryService[BusinessWall]
):
    """Service for BusinessWall operations.

    Provides high-level business logic for managing Business Walls.
    """

    repository_type = BusinessWallRepository


@service
class SubscriptionService(
    FlaskServiceMixin, SQLAlchemySyncRepositoryService[Subscription]
):
    """Service for Subscription operations.

    Handles subscription creation, updates, and payment tracking.
    """

    repository_type = SubscriptionRepository


@service
class RoleAssignmentService(
    FlaskServiceMixin, SQLAlchemySyncRepositoryService[RoleAssignment]
):
    """Service for RoleAssignment operations.

    Manages role assignments and invitation workflow.
    """

    repository_type = RoleAssignmentRepository


@service
class RolePermissionService(
    FlaskServiceMixin, SQLAlchemySyncRepositoryService[RolePermission]
):
    """Service for RolePermission operations.

    Manages granular permissions for PR Managers.
    """

    repository_type = RolePermissionRepository


@service
class PartnershipService(
    FlaskServiceMixin, SQLAlchemySyncRepositoryService[Partnership]
):
    """Service for Partnership operations.

    Manages PR Agency partnerships and invitation workflow.
    """

    repository_type = PartnershipRepository


@service
class BWContentService(FlaskServiceMixin, SQLAlchemySyncRepositoryService[BWContent]):
    """Service for BWContent operations.

    Manages Business Wall content and configuration.
    """

    repository_type = BWContentRepository


__all__ = [
    "BWContentService",
    "BusinessWallService",
    "PartnershipService",
    "RoleAssignmentService",
    "RolePermissionService",
    "SubscriptionService",
]
