"""Publication status enumeration for content lifecycle management."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from enum import StrEnum, auto


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

    @property
    def label(self) -> str:
        labels = {
            PublicationStatus.DRAFT: "Draft",
            PublicationStatus.PRIVATE: "Privé",
            PublicationStatus.PENDING: "En attente",
            PublicationStatus.PUBLIC: "Publié",
            PublicationStatus.REJECTED: "Refusé",
            PublicationStatus.EXPIRED: "Expiré",
            PublicationStatus.ARCHIVED: "Archivé",
            PublicationStatus.DELETED: "Supprimé",
        }
        return labels.get(self, str(self.value))

    @classmethod
    def from_str(cls, value: str) -> PublicationStatus | None:
        if not value:
            return None
        try:
            return cls(value.lower())
        except (ValueError, KeyError):
            return None

