"""KYC and authentication admin views."""

# Copyright (c) 2024, Abilian SAS & TCA
from __future__ import annotations

from typing import ClassVar

from sqladmin import Admin, ModelView

from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation


class UserAdmin(ModelView, model=User):
    """Admin interface for User model."""

    name = "Utilisateur"
    name_plural = "Utilisateurs"
    icon = "fa-solid fa-user"
    category = "Auth / KYC"

    can_delete = False

    # List view
    column_list: ClassVar = [User.id, User.last_name, User.first_name]

    # Details view
    column_details_exclude_list: ClassVar = [User.password]

    # Edit view
    form_excluded_columns: ClassVar = [User.password]


class OrganisationAdmin(ModelView, model=Organisation):
    """Admin interface for Organisation model."""

    icon = "fa-solid fa-building"
    category = "Auth / KYC"

    # List view
    column_list: ClassVar = [Organisation.id, Organisation.name]

    # Edit view
    form_excluded_columns: ClassVar = [Organisation.members]


class ProfileAdmin(ModelView, model=KYCProfile):
    """Admin interface for KYC Profile model."""

    name = "Profil KYC"
    name_plural = "Profils KYC"
    icon = "fa-solid fa-user"
    category = "Auth / KYC"

    can_delete = False

    # List view
    column_list: ClassVar = [KYCProfile.id, KYCProfile.user]


class RoleAdmin(ModelView, model=Role):
    """Admin interface for Role model."""

    icon = "fa-solid fa-user"
    category = "Auth / KYC"

    # List view
    column_list: ClassVar = [Role.id, Role.name]


def register(admin: Admin) -> None:
    """Register KYC-related admin views.

    Args:
        admin: Admin instance to register views to.
    """
    admin.add_view(UserAdmin)
    admin.add_view(OrganisationAdmin)
    admin.add_view(ProfileAdmin)
    # Broken
    # admin.add_view(RoleAdmin)
