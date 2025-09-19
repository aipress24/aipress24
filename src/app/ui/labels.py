# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from functools import singledispatch
from typing import Any

from app.enums import BWTypeEnum, OrganisationTypeEnum
from app.models.meta import get_label

LABELS_ORGANISATION_TYPE = {
    OrganisationTypeEnum.AUTO: "Non officialisée",
    OrganisationTypeEnum.MEDIA: "Média",
    OrganisationTypeEnum.COM: "PR agency",
    OrganisationTypeEnum.OTHER: "Autre",
    OrganisationTypeEnum.AGENCY: "Agence de presse",  # not detected in KYC structure
    # OrganisationTypeEnum.SYNDIC: "Syndicat ou fédération",  # not detected in KYC structure
    # OrganisationTypeEnum.INSTIT: "Média institutionnel",
}

LABELS_BW_TYPE = {
    BWTypeEnum.AGENCY: str(BWTypeEnum.AGENCY),
    BWTypeEnum.MEDIA: str(BWTypeEnum.MEDIA),
    BWTypeEnum.MICRO: str(BWTypeEnum.MICRO),
    BWTypeEnum.CORPORATE: str(BWTypeEnum.CORPORATE),
    BWTypeEnum.PRESSUNION: str(BWTypeEnum.PRESSUNION),
    BWTypeEnum.COM: str(BWTypeEnum.COM),
    BWTypeEnum.ORGANISATION: str(BWTypeEnum.ORGANISATION),
    BWTypeEnum.TRANSFORMER: str(BWTypeEnum.TRANSFORMER),
    BWTypeEnum.ACADEMICS: str(BWTypeEnum.ACADEMICS),
}


@singledispatch
def make_label(obj: Any) -> str:
    return get_label(obj.__class__) or "???"


@make_label.register
def _make_label_orga(obj: OrganisationTypeEnum) -> str:
    return LABELS_ORGANISATION_TYPE[obj]


@make_label.register
def _make_label_bw(obj: BWTypeEnum) -> str:
    return LABELS_BW_TYPE[obj]
