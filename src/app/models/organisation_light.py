# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Light organisations

Basically, a name of organisation declared by a user at KYC registration.

Light organisations proposal come from:
    - "orga_newsrooms" ontology, KYC field nom_media : family "media"
    - no ontology, KYC field nom_media_instit : family "instit"
    - 'agence_rp' ontology, KYC field nom_agence_rp : family "rp"
    - "groupes cotés") ontology, KYC field nom_orga : family "autre"
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import OrganisationFamilyEnum
from app.models.base import Base
from app.models.mixins import LifeCycleMixin

LIGHT_ORGS_TYPE_MAP = {str(x): x.name for x in OrganisationFamilyEnum}  # type:ignore
# ie:
# { "Médias" : "MEDIA', ... }

LIGHT_ORGS_FAMILY_LABEL = {
    "MEDIA": "Média",
    "AG_PRESSE": "Agence de presse",  # , not detected in KYC structure
    "SYNDIC": "Syndicat ou fédération",  # not detected in KYC structure
    "INSTIT": "Média institutionnel",
    "RP": "RP agency",
    "AUTRE": "Autre",
}


class LightOrganisation(LifeCycleMixin, Base):
    """
    - name: String unique
    - family: String
    """

    __tablename__ = "organisation_light"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String, unique=True, index=True)
    family: Mapped[str] = mapped_column(sa.String)
