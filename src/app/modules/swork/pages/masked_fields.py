# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations


class MaskFields:
    """MaskFields could be a simple list.
    We use this class to easier test and debug.
    """

    def __init__(self) -> None:
        self.masked_fields: set[str] = set()
        self.story: str = ""

    def add_field(self, field: str) -> None:
        self.masked_fields.add(field)

    def remove_field(self, field: str) -> None:
        self.masked_fields.discard(field)

    def add_message(self, message: str) -> None:
        if self.story:
            self.story += ", "
        self.story += message

    @property
    def masked(self) -> set[str]:
        return self.masked_fields
