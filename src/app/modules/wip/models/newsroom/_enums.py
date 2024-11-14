# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from enum import StrEnum


class TypeAvis(StrEnum):
    AVIS_D_ENQUETE = "Avis d’enquête"
    APPEL_A_TEMOIN = "Appel à témoin"
    APPEL_A_EXPERT = "Appel à expert"
