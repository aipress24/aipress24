# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import select

from app.enums import OrganisationFamilyEnum
from app.flask.extensions import db
from app.models.organisation_light import LightOrganisation


def get_organisation_family(
    family: OrganisationFamilyEnum = OrganisationFamilyEnum.AUTRE,  # type: ignore
) -> list[str]:
    """Get list of light organisation of specified family"""
    query = (
        select(LightOrganisation)
        .where(LightOrganisation.family == family.name)
        .order_by(LightOrganisation.name)
    )
    result = db.session.execute(query).scalars()
    return [org.name for org in result]


def get_organisation_choices_family(
    family: OrganisationFamilyEnum = OrganisationFamilyEnum.AUTRE,  # type: ignore
) -> list[tuple[str, str]]:
    """Get list of light organisations of specified famille in HTML select format"""
    return [(name, name) for name in get_organisation_family(family)]


def store_light_organisation(
    name: str = "",
    family: OrganisationFamilyEnum = OrganisationFamilyEnum.AUTRE,  # type: ignore
) -> bool:
    name = str(name).strip()
    if not name:
        return False
    db_session = db.session
    query = select(LightOrganisation).where(LightOrganisation.name == name)
    found_orga_light = db.session.execute(query).scalar()
    if found_orga_light:
        return False
    db_session.add(LightOrganisation(name=name, family=family.name))
    db_session.commit()
    return True
