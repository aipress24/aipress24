"""Repository pattern implementations for data access."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections.abc import Sequence

from advanced_alchemy.filters import LimitOffset, OrderBy
from flask_super.decorators import service
from sqlalchemy import false, true
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.models.auth import Role, User
from app.models.email_log import EmailLog
from app.models.organisation import Organisation
from app.services.repositories import Repository


#
# Auth models
#
@service
class UserRepository(Repository[User]):
    model_type = User

    @staticmethod
    def public_member_filters() -> list[ColumnElement[bool]]:
        """Filters for members listable in the public directory: active, not a
        clone, not soft-deleted. Shared with the swork members directory so the
        site and the public API agree on exactly who is listable.
        """
        return [
            User.active == true(),
            User.is_clone == false(),
            User.deleted_at.is_(None),
        ]

    def list_public_members(
        self, *, limit: int, offset: int
    ) -> tuple[Sequence[User], int]:
        """One page of public member profiles plus the total count."""
        return self.list_and_count(
            *self.public_member_filters(),
            LimitOffset(limit, offset),
            OrderBy(User.id, "desc"),
            load=[selectinload(User.profile), selectinload(User.organisation)],
        )

    def get_public_member(self, identifier: int) -> User | None:
        """A single public member profile, or None if not publicly listable."""
        return self.get_one_or_none(
            User.id == identifier,
            *self.public_member_filters(),
            load=[selectinload(User.profile), selectinload(User.organisation)],
        )


@service
class RoleRepository(Repository[Role]):
    model_type = Role

    def get_by_name(self, name: str) -> Role:
        return self.get_one(Role.name == name)


#
# Social models
#
@service
class OrganisationRepository(Repository[Organisation]):
    model_type = Organisation

    @staticmethod
    def public_filters() -> list[ColumnElement[bool]]:
        """Organisations visible in the public directory: not soft-deleted
        (mirrors swork OrganisationsList and search.adapters.is_public).
        """
        return [Organisation.deleted_at.is_(None)]

    def list_public(
        self, *, limit: int, offset: int
    ) -> tuple[Sequence[Organisation], int]:
        """One page of public organisations plus the total count."""
        return self.list_and_count(
            *self.public_filters(),
            LimitOffset(limit, offset),
            OrderBy(Organisation.id, "desc"),
        )

    def get_public(self, identifier: int) -> Organisation | None:
        """A single public organisation, or None if not publicly listable."""
        return self.get_one_or_none(
            Organisation.id == identifier, *self.public_filters()
        )


@service
class EmailLogRepository(Repository[EmailLog]):
    model_type = EmailLog
