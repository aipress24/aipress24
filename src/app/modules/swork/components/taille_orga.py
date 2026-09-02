# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The « taille d'organisation » filter, shared by two directories.

The members directory reads the size off `KYCProfile`, the organisations
directory off `BusinessWall` — different models, so each keeps its own
`__init__` and `apply`. Everything else was written twice: the sort key
byte for byte, the label with two different apostrophes, and an
`active_options` override that differed only by `state[i]` versus
`state.get(i)` (audit 2026-09-02).
"""

from __future__ import annotations

from typing import cast

from .base import Filter, FilterOption

#: The ontology's open-ended bucket, sorted last.
UNBOUNDED = "+"
_UNBOUNDED_SORT = 999_999_999
#: A code the ontology no longer knows — sorted after every real size,
#: before the open-ended bucket.
_UNKNOWN_SORT = 999_999


def taille_orga_sort_key(code: str) -> int:
    """Sort key for taille_organisation codes in ascending numeric order."""
    if code == UNBOUNDED:
        return _UNBOUNDED_SORT
    try:
        return int(code)
    except ValueError:
        return _UNKNOWN_SORT


def taille_orga_label(value: str) -> str:
    """Turn a raw ontology code (« 1 », « 49 », « + ») into a label.

    The two directories had their own copy and had already drifted: one
    rendered « Jusqu'à » with a straight apostrophe, the other « Jusqu’à »
    with a typographic one. The typographic form wins — it is what the
    KYC ontology writes and what the tests pin.
    """
    if value == UNBOUNDED:
        # The ontology's largest bounded bucket is 1000000.
        return "Plus de 1 000 000"
    if value == "1":
        return "1 personne"
    try:
        return f"Jusqu’à {int(value)}"
    except ValueError:
        return value


class TailleOrgaFilter(Filter):
    """Options are `FilterOption(label, code)`; the wire carries the code.

    Keeping the raw ontology code on the wire means URL state stays
    stable across label tweaks.
    """

    id = "taille_organisation"
    label = "Tailles d’organisation"

    def active_options(self, state: dict[str, bool]) -> list[str | FilterOption]:
        """The selected **codes**, where the base class returns options.

        The return type stays the base's `list[str | FilterOption]`
        rather than the narrower `list[str]` these codes really are:
        `list` is invariant, so narrowing it would break substitution.

        `.get` rather than `state[...]`: `state` is posted by the form
        and can be shorter than `options`, so indexing it would raise.
        """
        codes: list[str | FilterOption] = []
        for i in range(len(state)):
            if state.get(str(i)):
                codes.append(cast("FilterOption", self.options[i]).code)
        return codes
