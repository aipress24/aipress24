# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

from flask import render_template_string
from markupsafe import Markup

from app.flask.lib.macros import macro

COLUMN = [
    "name",
    {"name": "brand.name", "label": "Brand"},
    "price",
    {"name": "sku", "label": "SKU"},
    {"name": "qty", "label": "QTY"},
]

LINES = [
    {
        "url": "#",
        "columns": [
            {"value": "Self-enabling grid-enabled adapter"},
            {"value": "Quitzon, Mante and Braun"},
            {"value": "123 Euros"},
            {"value": "25733464"},
            {"value": 15},
        ],
    },
    {
        "url": "#",
        "columns": [
            {"value": "Light Bulb"},
            {"value": "Jones & Perkins"},
            {"value": "12 Euros"},
            {"value": "12333234"},
            {"value": 135},
        ],
    },
]

#
DOWNLOAD = """
<a class="" target="_blank" rel="noreferrer noopener" arialabel="XXX" href="{value}">
    <div class="e4rLWCQ _1DtaAoI">
        <span class="FPMjOVo">
            <span style="width: 16px; height: 16px; fill: rgb(122, 125, 133);" aria-label="XXX" role="img">
                <svg width="12" height="14" viewBox="0 0 12 14" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" clip-rule="evenodd" d="M6.28124 10.875C6.1979 10.9583 6.10415 11 5.99999 11C5.89582 11 5.80207 10.9583 5.71874 10.875L1.125 6.24999C1.04166 6.18749 0.999998 6.10415 0.999998 5.99999C0.999998 5.89582 1.03125 5.80207 1.09375 5.71874L1.71875 5.09374C1.80208 5.03124 1.89583 4.99999 2 4.99999C2.10416 4.99999 2.18749 5.04165 2.24999 5.12499L5.18749 8.15623V0.374999C5.18749 0.270833 5.22395 0.182291 5.29686 0.109375C5.36978 0.0364584 5.45832 0 5.56249 0H6.43748C6.54165 0 6.63019 0.0364584 6.70311 0.109375C6.77603 0.182291 6.81248 0.270833 6.81248 0.374999V8.15623L9.74998 5.12499C9.81248 5.04165 9.89581 4.99999 9.99998 4.99999C10.1041 4.99999 10.1979 5.03124 10.2812 5.09374L10.875 5.71874C10.9583 5.80207 11 5.89582 11 5.99999C11 6.10415 10.9687 6.18749 10.9062 6.24999L6.28124 10.875ZM11.625 12.375C11.7291 12.375 11.8177 12.4114 11.8906 12.4843C11.9635 12.5573 12 12.6458 12 12.75V13.625C12 13.7291 11.9635 13.8177 11.8906 13.8906C11.8177 13.9635 11.7291 14 11.625 14H0.374999C0.270833 14 0.182291 13.9635 0.109375 13.8906C0.0364584 13.8177 0 13.7291 0 13.625V12.75C0 12.6458 0.0364584 12.5573 0.109375 12.4843C0.182291 12.4114 0.270833 12.375 0.374999 12.375H11.625Z"></path></svg>
            </span>
        </span>
    </div>
</a>
"""


def make_columns(columns):
    result = []
    for item in columns:
        match item:
            case str(name):
                # static analysis: ignore[undefined_name]
                result.append({"name": name, "label": name.capitalize()})
            case {"name": _name, "label": _label, **__}:
                result.append(item)
            case _:
                msg = f"Can't match value {item}"
                raise ValueError(msg)

    return result


def format_value(obj):
    match obj:
        case str(value):
            return value
        case {"type": "download", "value": value}:
            return Markup(DOWNLOAD.format(value=value))
        case int(value):
            return str(value)
        case float(value):
            return f"{value:.2f}"
        case {"value": obj}:
            return format_value(obj)
        case _:
            msg = f"Can't match value {obj}"
            raise ValueError(msg)


@macro
def make_table(table: dict) -> str:
    columns = make_columns(table["specs"]["columns"])
    ctx = {
        "spec": {"columns": columns},
        "lines": table["lines"],
        "present_value": format_value,
    }
    template_str = (Path(__file__).parent / "table.j2").read_text()
    return Markup(render_template_string(template_str, **ctx))


@macro
def make_table2(table: dict) -> str:
    specs = table["specs"]
    columns = make_columns(specs["columns"])
    ctx = {
        "specs": {
            "columns": columns,
            "data_source": specs["data_source"],
        },
        "lines": table["lines"],
        "present_value": format_value,
    }
    template_str = (Path(__file__).parent / "table2.j2").read_text()
    return Markup(render_template_string(template_str, **ctx))


@macro
def make_table3(table: dict) -> str:
    # specs = table["specs"]
    # columns = make_colums(specs["columns"])
    ctx = {
        "table": table,
    }
    template_str = (Path(__file__).parent / "table3.j2").read_text()
    return Markup(render_template_string(template_str, **ctx))
