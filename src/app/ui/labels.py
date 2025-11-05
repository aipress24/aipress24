"""Label generation utilities for UI display."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from functools import singledispatch
from typing import Any

from app.enums import BWTypeEnum, OrganisationTypeEnum, ProfileEnum
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

LABELS_PROFILE = {
    ProfileEnum.PM_DIR: "Dirigeant de média",
    ProfileEnum.PM_JR_CP_SAL: "Journaliste salarié avec CP",
    ProfileEnum.PM_JR_PIG: "Journaliste salarié sans CP",
    ProfileEnum.PM_JR_CP_ME: "Journaliste avec CP en ME",
    ProfileEnum.PM_JR_ME: "Journaliste sans CP en ME",
    ProfileEnum.PM_DIR_INST: "Dirigeant de média institutionnel",
    ProfileEnum.PM_JR_INST: "Journaliste institutionnel",
    ProfileEnum.PM_DIR_SYND: "Dirigeant d'une fédération",
    ProfileEnum.PR_DIR: "Dirigeant d'une press relatiopn agency",
    ProfileEnum.PR_CS: "Consultant dans une press relatiopn agency",
    ProfileEnum.PR_CS_IND: "Consultant indépendant en relation presse",
    ProfileEnum.PR_DIR_COM: "Directeur d'un service de communication",
    ProfileEnum.PR_CS_COM: "Consultant dans un service de communication",
    ProfileEnum.XP_DIR_ANY: "Dirigeant ou élu",
    ProfileEnum.XP_ANY: "Expert ou consultant salarié",
    ProfileEnum.XP_PR: "Expert responsable relation presse",
    ProfileEnum.XP_IND: "Expert indépendant",
    ProfileEnum.XP_DIR_SU: "Dirigeant d'une start-up",
    ProfileEnum.XP_INV_PUB: "Investisseur pub dans la presse",
    ProfileEnum.XP_DIR_EVT: "Dirigeant d'une entité événementiel",
    ProfileEnum.TP_DIR_ORG: "Dirigeant service et conseils transformation",
    ProfileEnum.TR_CS_ORG: "Consultant service et conseils transformation",
    ProfileEnum.TR_CS_ORG_PR: "Consultant responsable presse dans service transformation",
    ProfileEnum.TR_CS_ORG_IND: "Consultant en transformation des organisations",
    ProfileEnum.TR_DIR_SU_ORG: "Dirigeant start-up transformation des organisations",
    ProfileEnum.TR_INV_ORG: "Investisseur innovation transformation des organisations",
    ProfileEnum.TR_DIR_POLE: "Dirigeant pôle de compétitivité",
    ProfileEnum.AC_DIR: "Dirigeant enseignement supérieur",
    ProfileEnum.AC_DIR_JR: "Dirigeant école journalisme",
    ProfileEnum.AC_ENS: "Enseignant chercheur",
    ProfileEnum.AC_DOC: "Doctorant",
    ProfileEnum.AC_ST: "Étudiant",
    ProfileEnum.AC_ST_ENT: "Étudiant entrepreneur",
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


@make_label.register
def _make_label_profile(obj: ProfileEnum) -> str:
    return LABELS_PROFILE[obj]
