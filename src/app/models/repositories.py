"""Repository pattern implementations for data access."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.decorators import service

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


@service
class EmailLogRepository(Repository[EmailLog]):
    model_type = EmailLog
