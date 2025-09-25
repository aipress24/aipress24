"""Publication status enumeration for content lifecycle management."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from aenum import StrEnum, auto


class PublicationStatus(StrEnum):
    """Enum representing the publication status of content items."""

    DRAFT = auto()
    PRIVATE = auto()
    PENDING = auto()
    PUBLIC = auto()
    REJECTED = auto()
    EXPIRED = auto()
    ARCHIVED = auto()
    DELETED = auto()
