# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys
from functools import cached_property
from pathlib import Path
from typing import Any

from flask import current_app
from markupsafe import Markup
from wtforms import widgets
from wtforms.fields.choices import SelectMultipleField


def convert_to_tom_choices_js(choices: list | dict) -> list[dict[str, Any]]:
    if isinstance(choices, list):
        # required by choices.js : list of dict
        return [
            {
                "value": item[0] if isinstance(item, (list, tuple)) else str(item),
                "label": item[1] if isinstance(item, (list, tuple)) else str(item),
            }
            for item in choices
        ]
    if isinstance(choices, dict):
        # dict is a dict of groups of labels:
        return _dict_to_group_tom_choices(choices)
    print(f"{type(choices)}", file=sys.stderr)
    print(f"{choices=}", file=sys.stderr)
    raise TypeError


def _dict_to_group_tom_choices(choices: dict) -> list[dict[str, Any]]:
    groups = []
    for group, items in choices.items():
        choices_group = [
            {
                "optgroup": group,
                "value": item[0] if isinstance(item, (list, tuple)) else str(item),
                "label": item[1] if isinstance(item, (list, tuple)) else str(item),
            }
            for item in items
        ]
        groups.extend(choices_group)

    return groups


class SelectMultiSimpleWidget(widgets.Select):
    def __call__(self, field: SelectMultiSimpleField, **kwargs):
        template = self.get_template()
        # #0162: return Markup, not bare str (see CountrySelectWidget).
        return Markup(template.render(field=field))

    def get_template(self):
        template_path = Path(__file__).parent / "select_multi_simple.j2"
        return current_app.jinja_env.from_string(template_path.read_text())


class SelectMultiSimpleField(SelectMultipleField):
    widget = SelectMultiSimpleWidget()

    def __init__(
        self,
        **kwargs,
    ) -> None:
        self.lock = kwargs.pop("readonly", False)
        super().__init__(**kwargs)
        self.multiple = True
        self.create = False
        self.choices = kwargs["choices"]

    @cached_property
    def _taxonomy_map(self) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        raw = self.choices or []
        if isinstance(raw, list):
            for item in raw:
                val = item[0] if isinstance(item, (list, tuple)) else str(item)
                val_clean = val.strip()
                mapping.setdefault(val_clean.lower(), []).append(val_clean)
                if "/" in val_clean:
                    _, suffix = val_clean.split("/", 1)
                    mapping.setdefault(suffix.strip().lower(), []).append(val_clean)
        elif isinstance(raw, dict):
            for _group, items in raw.items():
                for item in items:
                    val = item[0] if isinstance(item, (list, tuple)) else str(item)
                    val_clean = val.strip()
                    mapping.setdefault(val_clean.lower(), []).append(val_clean)
                    if "/" in val_clean:
                        _, suffix = val_clean.split("/", 1)
                        mapping.setdefault(suffix.strip().lower(), []).append(val_clean)
        return mapping

    def _resolve_values(self) -> list[str]:
        raw = self.data
        if not raw:
            return []
        if isinstance(raw, str):
            raw = [raw]
        resolved: list[str] = []
        seen: set[str] = set()
        for val in raw:
            if not val or not str(val).strip():
                continue
            val_clean = str(val).strip()
            matches = self._taxonomy_map.get(val_clean.lower())
            if matches:
                for tax_val in matches:
                    if tax_val not in seen:
                        seen.add(tax_val)
                        resolved.append(tax_val)
            elif "/" in val_clean:
                _, suffix = val_clean.split("/", 1)
                suf_matches = self._taxonomy_map.get(suffix.strip().lower())
                if suf_matches:
                    for tax_val in suf_matches:
                        if tax_val not in seen:
                            seen.add(tax_val)
                            resolved.append(tax_val)
                elif val_clean not in seen:
                    seen.add(val_clean)
                    resolved.append(val_clean)
            elif val_clean not in seen:
                seen.add(val_clean)
                resolved.append(val_clean)
        return resolved

    def get_tom_choices_for_js(self) -> list[dict[str, Any]]:
        base = convert_to_tom_choices_js(self.choices)
        known_values = {opt["value"] for opt in base}
        for val in self._resolve_values():
            if val not in known_values:
                known_values.add(val)
                base.append({"value": val, "label": val})
        return base

    def get_data(self) -> list[str]:
        return self._resolve_values()
