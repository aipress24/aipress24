# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from arrow import Arrow
from flask_security import hash_password
from sqlalchemy_utils.types.arrow import arrow

from app.flask.extensions import db
from app.models.auth import KYCProfile, User
from app.models.repositories import RoleRepository, UserRepository


def decimal_constructor(loader, node) -> Decimal:
    value = loader.construct_scalar(node)
    return Decimal(value)


def decimal_constructor_sequence(loader, node) -> Decimal:
    value = loader.construct_sequence(node)
    return Decimal(value[0])


def arrow_constructor(loader, node) -> Arrow:
    value = loader.construct_scalar(node)
    return arrow.get(value)


def arrow_constructor_mapping(loader, node) -> Arrow:
    value = loader.construct_mapping(node)
    return arrow.get(value["_datetime"])


def datetime_constructor(loader, node) -> datetime:
    value = loader.construct_scalar(node)
    return datetime.fromisoformat(value)


yaml.SafeLoader.add_constructor("!decimal", decimal_constructor)
yaml.SafeLoader.add_constructor("!Decimal", decimal_constructor)
yaml.SafeLoader.add_constructor("!datetime", datetime_constructor)
yaml.SafeLoader.add_constructor("!arrow", arrow_constructor)
yaml.SafeLoader.add_constructor(
    "tag:yaml.org,2002:python/object:arrow.arrow.Arrow",
    arrow_constructor_mapping,
)
yaml.SafeLoader.add_constructor(
    "tag:yaml.org,2002:python/object/apply:decimal.Decimal",
    decimal_constructor_sequence,
)


def load_user_data(source: str | Path) -> dict[str, Any]:
    with Path(source).open() as f:
        return yaml.load(f, Loader=yaml.SafeLoader)


def import_user(source: str | Path) -> User:
    data = load_user_data(source)
    session = db.session

    user_repo = UserRepository(session=session)
    role_repo = RoleRepository(session=session)

    _is_merge = False
    if "id" in data:
        _user_id = data["id"]
        if user_repo.count(id=_user_id):
            _is_merge = True
    if not _is_merge and "id" in data:
        del data["id"]

    password = data.pop("_password", None)
    roles_data = set(data.pop("_roles", []))
    role_name = data.pop("_role", None)
    profile_data = data.pop("_profile")
    if "id" in profile_data:
        del profile_data["id"]
    is_admin = data.pop("_is_admin", False)

    user = User(**data)
    if password:
        user.password = hash_password(password)

    profile = KYCProfile(**profile_data)
    user.profile = profile

    if _is_merge:
        user_repo.update(user)
    else:
        user_repo.add(user)

    if role_name:
        roles_data.add(role_name)
    if is_admin:
        roles_data.add("ADMIN")
    for role_string in roles_data:
        role = role_repo.get_by_name(role_string)
        user.roles.append(role)

    session.commit()
    return user
