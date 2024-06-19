# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from aenum import StrEnum, auto


class PublicationStatus(StrEnum):
    DRAFT = auto()
    PRIVATE = auto()
    PENDING = auto()
    PUBLIC = auto()
    REJECTED = auto()
    EXPIRED = auto()
    ARCHIVED = auto()
    DELETED = auto()
