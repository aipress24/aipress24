# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections.abc import Callable
from functools import singledispatch

from app.enums import OrganisationFamilyEnum
from app.models.auth import User
from app.models.organisation import Organisation
from app.services.roles import Role, has_role

from ._constants import (
    REPUT_COM_SPEC,
    REPUT_GENERIC_ORG_SPEC,
    REPUT_GENERIC_USER_SPEC,
    REPUT_JOURNALIST_SPEC,
    REPUT_MEDIA_SPEC,
)
from ._functions import export_functions
from ._types import Real, Spec


@singledispatch
def compute_reputation(obj: User | Organisation) -> dict[str, Real]:
    """Compute the reputation of a user / org."""
    if isinstance(obj, User):
        return compute_reputation_user(obj)
    elif isinstance(obj, Organisation):
        return compute_reputation_org(obj)
    else:
        # Should not happen
        return {"total": 0}


@compute_reputation.register
def compute_reputation_user(user: User) -> dict[str, Real]:
    """Compute the reputation of a user."""
    if has_role(user, Role.PRESS_MEDIA):
        # TODO: ajouter le rôle "redac' chef"
        return compute_reputation_with_spec(user, REPUT_JOURNALIST_SPEC)
    elif has_role(user, Role.PRESS_RELATIONS) or has_role(user, Role.EXPERT):
        return compute_reputation_with_spec(user, REPUT_GENERIC_USER_SPEC)
    else:
        return {"total": 0}


@compute_reputation.register
def compute_reputation_org(org: Organisation) -> dict[str, Real]:
    """Compute the reputation of an organisation."""
    match org.type:
        case (
            OrganisationFamilyEnum.MEDIA
            | OrganisationFamilyEnum.AG_PRESSE
            | OrganisationFamilyEnum.SYNDIC
        ):
            spec = REPUT_MEDIA_SPEC
        case OrganisationFamilyEnum.RP:
            spec = REPUT_COM_SPEC
        case _:
            spec = REPUT_GENERIC_ORG_SPEC
    return compute_reputation_with_spec(org, spec)


def compute_reputation_with_spec(obj, spec: Spec) -> dict[str, Real]:
    functions = export_functions()
    total = 0.0
    details = {}
    for key, _tag, ponderation in spec:
        func: Callable[[object], int | float] | None = functions.get(key)
        if not func:
            continue
        value = func(obj)
        details[key] = value
        total += ponderation * value

    details["total"] = total
    return details
