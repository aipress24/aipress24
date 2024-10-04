# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from functools import singledispatch
from typing import Any

from app.enums import OrganisationFamilyEnum
from app.models.meta import get_label

LABELS = {
    OrganisationFamilyEnum.MEDIA: "Média",
    OrganisationFamilyEnum.AG_PRESSE: "Agence de presse",  # not detected in KYC structure
    OrganisationFamilyEnum.SYNDIC: "Syndicat ou fédération",  # not detected in KYC structure
    OrganisationFamilyEnum.INSTIT: "Média institutionnel",
    OrganisationFamilyEnum.RP: "RP agency",
    OrganisationFamilyEnum.AUTRE: "Autre",
}


@singledispatch
def make_label(obj: Any) -> str:
    return get_label(obj.__class__) or "???"


@make_label.register
def _make_label(obj: OrganisationFamilyEnum) -> str:
    return LABELS[obj]
