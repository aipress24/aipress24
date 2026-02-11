# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Role assignment and permission models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

import sqlalchemy as sa
from advanced_alchemy.base import UUIDAuditBase
from advanced_alchemy.types import GUID
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .business_wall import BusinessWallPoc


class BWRoleType(StrEnum):
    """Business Wall role types (RBAC)."""

    BW_OWNER = "BW_OWNER"  # Business Wall Owner
    BWMI = "BWMi"  # Business Wall Manager (internal)
    BWPRI = "BWPRi"  # PR Manager (internal)
    BWME = "BWMe"  # Business Wall Manager (external)
    BWPRE = "BWPRe"  # PR Manager (external)


class InvitationStatus(StrEnum):
    """Invitation status for role assignments."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PermissionType(StrEnum):
    """Permission types for PR Managers (Stage 6 missions)."""

    PRESS_RELEASE = "press_release"
    EVENTS = "events"
    MISSIONS = "missions"
    PROFILES = "profiles"
    MEDIA_CONTACTS = "media_contacts"
    STATS_KPI = "stats_kpi"
    MESSAGES = "messages"


class RoleAssignmentPoc(UUIDAuditBase):
    """Role assignment for Business Wall access control.

    Maps users to roles within a Business Wall, with invitation workflow.
    """

    __tablename__ = "poc_role_assignment"

    # Foreign keys
    business_wall_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("poc_business_wall.id", ondelete="CASCADE"), nullable=False
    )
    business_wall: Mapped[BusinessWallPoc] = relationship(
        back_populates="role_assignments"
    )

    # User reference - references User ID (no FK constraint for POC)
    user_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    # Role information
    role_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Invitation workflow
    invitation_status: Mapped[str] = mapped_column(
        String(20), default=InvitationStatus.PENDING.value
    )
    invited_at: Mapped[datetime | None] = mapped_column(nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationship to permissions
    permissions: Mapped[list["RolePermissionPoc"]] = relationship(
        "RolePermissionPoc",
        back_populates="role_assignment",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<RoleAssignmentPoc {self.id} role={self.role_type} user_id={self.user_id}>"


class RolePermissionPoc(UUIDAuditBase):
    """Granular permissions for PR Manager roles (Stage 6 missions).

    Allows fine-grained control over what PR Managers can do.
    """

    __tablename__ = "poc_role_permission"

    # Foreign key to RoleAssignment
    role_assignment_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("poc_role_assignment.id", ondelete="CASCADE"), nullable=False
    )
    role_assignment: Mapped[RoleAssignmentPoc] = relationship(
        back_populates="permissions"
    )

    # Permission type
    permission_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Permission state
    is_granted: Mapped[bool] = mapped_column(default=False)

    def __repr__(self) -> str:
        status = "granted" if self.is_granted else "denied"
        return (
            f"<RolePermissionPoc {self.id} type={self.permission_type} status={status}>"
        )
