# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path
from typing import Any

from flask import current_app
from markupsafe import Markup
from wtforms import widgets
from wtforms.fields.choices import SelectMultipleField


def convert_dual_choices_js(choices: dict) -> dict:
    """Data structure:

    # Argument 'choices':
    #     {'Associations': ['Actions humanitaires', 'Communication et sensibilisatio ...
    #
    {
        "field1": [ ('Associations','Associations'), ...]
        "field2": [ ( 'Associations /Actions humanitaires',
                      'Associations / Actions humanitaires'), ...
    }

    Output:
    {
        "field1": [ {"value": 'Associations', "label": 'Associations'} ...
        "field2": [ {"value": 'Associations / Actions humanitaires',  "label":
            'Associations / Actions humanitaires'}, ...
    }
    """
    field1 = [
        {
            "value": val[0],
            "label": val[1],
        }
        for val in choices.get("field1", [])
    ]
    field2 = []
    field2_raw = choices.get("field2", {})
    if isinstance(field2_raw, dict):
        for values in field2_raw.values():
            for val in values:
                field2.append(
                    {
                        "value": val[0] if isinstance(val, (list, tuple)) else val,
                        "label": val[1] if isinstance(val, (list, tuple)) else val,
                    }
                )
    result = {"field1": field1, "field2": field2}
    return result


class DualSelectWidget(widgets.Select):
    def __call__(self, field: DualSelectField, **kwargs):
        # #0162: return Markup, not bare str (see CountrySelectWidget).
        template = self.get_template()
        return Markup(template.render(field=field))

    def get_template(self):
        template_path = Path(__file__).parent / "dual_select_multi.j2"
        return current_app.jinja_env.from_string(template_path.read_text())


class DualSelectField(SelectMultipleField):
    widget = DualSelectWidget()
    double_select = True

    def __init__(
        self,
        **kwargs,
    ) -> None:
        self.id2 = kwargs.pop("id2", "")
        self.name2 = kwargs.pop("name2", "")
        self.label2 = kwargs.pop("label2", "")
        self.lock = kwargs.pop("readonly", False)
        super().__init__(**kwargs)
        self.multiple = True
        self.create = False
        self.data2 = kwargs.pop("data2", "")

    @cached_property
    def _taxonomy_detail_map(self) -> dict[str, list[str]]:
        raw = self.choices or {}
        field2 = raw.get("field2", {})
        mapping: dict[str, list[str]] = {}
        if isinstance(field2, dict):
            for items in field2.values():
                for item in items:
                    val = item[0] if isinstance(item, (list, tuple)) else item
                    if "/" in val:
                        _, detail = val.split("/", 1)
                        mapping.setdefault(detail.strip().lower(), []).append(val)
                    mapping.setdefault(val.strip().lower(), []).append(val)
        return mapping

    @cached_property
    def _taxonomy_parent_map(self) -> dict[str, str]:
        raw = self.choices or {}
        field1 = raw.get("field1", [])
        mapping: dict[str, str] = {}
        for item in field1:
            val = item[0] if isinstance(item, (list, tuple)) else item
            mapping[val.strip().lower()] = val
        return mapping

    def _resolve_detail_values(self) -> list[str]:
        raw = self.data2
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
            exact_matches = self._taxonomy_detail_map.get(val_clean.lower())
            if exact_matches:
                for tax_val in exact_matches:
                    if tax_val not in seen:
                        seen.add(tax_val)
                        resolved.append(tax_val)
            elif "/" in val_clean:
                _, detail = val_clean.split("/", 1)
                det_matches = self._taxonomy_detail_map.get(detail.strip().lower())
                if det_matches:
                    for tax_val in det_matches:
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

    def _resolve_parent_values(self) -> list[str]:
        raw = self.data
        if isinstance(raw, str):
            raw = [raw]
        elif not raw:
            raw = []
        resolved: list[str] = []
        seen: set[str] = set()

        for det in self._resolve_detail_values():
            if "/" in det:
                parent = det.split("/", 1)[0].strip()
                if parent not in seen:
                    seen.add(parent)
                    resolved.append(parent)

        for val in raw:
            if not val or not str(val).strip():
                continue
            val_clean = str(val).strip()
            canonical = self._taxonomy_parent_map.get(val_clean.lower())
            if canonical and canonical not in seen:
                seen.add(canonical)
                resolved.append(canonical)
            elif not resolved and val_clean not in seen:
                seen.add(val_clean)
                resolved.append(val_clean)

        return resolved

    def get_dual_tom_choices_for_js(self) -> dict[str, Any]:
        """Data structure:

        # Input:
        #     {'Associations': ['Actions humanitaires',
        #         'Communication et sensibilisatio ...

        Output:
        {
            "field1": [ {"value": 'Associations', "label": 'Associations'} ...
            "field2": [ {"value": 'Associations / Actions humanitaires',  "label":
                'Associations / Actions humanitaires'} ...
        }
        """
        base = convert_dual_choices_js(self.choices or {})
        known_parents = {p["value"] for p in base["field1"]}
        known_children = {c["value"] for c in base["field2"]}

        for parent in self._resolve_parent_values():
            if parent not in known_parents:
                known_parents.add(parent)
                base["field1"].append({"value": parent, "label": parent})

        for detail in self._resolve_detail_values():
            if detail not in known_children:
                known_children.add(detail)
                base["field2"].append({"value": detail, "label": detail})
                if "/" in detail:
                    parent = detail.split("/", 1)[0].strip()
                    if parent not in known_parents:
                        known_parents.add(parent)
                        base["field1"].append({"value": parent, "label": parent})
        return base

    def get_data(self) -> str:
        return json.dumps(self._resolve_parent_values())

    def get_data2(self) -> str:
        return json.dumps(self._resolve_detail_values())
