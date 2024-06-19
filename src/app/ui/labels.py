# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from functools import singledispatch
from typing import Any

from app.models.meta import get_label
from app.models.orgs import OrganisationType

LABELS = {
    OrganisationType.AUTO: "Non-officialisée",
    OrganisationType.MEDIA: "Média",
    OrganisationType.COM: "Agence de Com'",
    OrganisationType.OTHER: "Autre",
    OrganisationType.AGENCY: "Agence de Presse",
}


@singledispatch
def make_label(obj: Any) -> str:
    return get_label(obj.__class__) or "???"


@make_label.register
def _make_label(obj: OrganisationType) -> str:
    return LABELS[obj]
