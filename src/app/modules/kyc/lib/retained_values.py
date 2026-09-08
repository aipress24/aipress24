# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Values a profile already holds stay selectable — bug #0333.

A taxonomy that drops or renames a term leaves every profile that used
it holding a value the current list no longer offers. The widget half
of the answer shipped first: the stored value is displayed. This is the
server half — the rule is « the current taxonomy **plus** what this
profile already carried », so a member can save a profile they did not
break, while a retired term stays impossible to pick afresh.

The widening is per-field and per-request: it only ever adds the values
this profile holds, never another's, and it is what both the option
list and `pre_validate` read, so the two cannot drift apart.
"""

from __future__ import annotations

from typing import Any

RETAINED_GROUP = "Valeurs de votre profil"


def choice_values(choices: Any) -> set[str]:
    """The values a `choices` list or optgroup dict offers.

    Both shapes reach the KYC fields — `get_choices` returns a flat
    list for a flat ontology and a group dict for a nested one — and
    each holds either `(value, label)` pairs or bare strings.
    """
    if isinstance(choices, dict):
        return {v for items in choices.values() for v in choice_values(items)}
    if not choices:
        return set()
    return {_value_of(item) for item in choices}


def _value_of(item: Any) -> str:
    if isinstance(item, (list, tuple)):
        return str(item[0]).strip()
    return str(item).strip()


class RetainsProfileValues:
    """Mixin: widen this field's choices with the values it already holds.

    Mixed in ahead of the WTForms field, so the inherited
    `pre_validate` checks against the widened list without knowing that
    anything was widened.
    """

    choices: Any

    def retain(self, values: Any) -> None:
        """Add `values` to the choices, minus those already offered."""
        known = choice_values(self.choices)
        missing = [v for v in _as_list(values) if v and v not in known]
        if not missing:
            return
        # Ordered dedup: a profile can hold the same value twice after a
        # taxonomy merge, and a duplicated option renders twice.
        seen: set[str] = set()
        extra = [(v, v) for v in missing if not (v in seen or seen.add(v))]
        if isinstance(self.choices, dict):
            self.choices = {**self.choices, RETAINED_GROUP: extra}
        else:
            self.choices = list(self.choices or []) + extra


def _as_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [values.strip()]
    if isinstance(values, (list, tuple, set)):
        return [str(v).strip() for v in values]
    return [str(values).strip()]


def retain_profile_values(form: Any, stored: dict[str, Any]) -> None:
    """Let every capable field on `form` keep the values `stored` holds.

    Called on both legs of the wizard: on GET right after the stored
    values are put on the fields, and on POST from the view — the POST
    leg builds the form from the submission alone, so without this the
    reference set would be gone exactly when validation needs it.
    """
    for name, value in stored.items():
        field = getattr(form, name, None)
        if isinstance(field, RetainsProfileValues):
            field.retain(value)
