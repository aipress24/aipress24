# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Utility to render SVG icons. Currently supported:

- "lucide": "https://github.com/lucide-icons/lucide.git",
- "heroicons": "https://github.com/tailwindlabs/heroicons.git",

"""

from __future__ import annotations

import re

from markupsafe import Markup

from app.flask.lib.macros import macro
from app.flask.util import get_home_path


@macro
def icon(name: str, type="solid", _class: str = "", **kw):
    if "/" in name:
        type, name = name.split("/")[0:2]
    if "@" in name:
        name, type = name.split("@")[0:2]

    path = get_home_path() / "icons" / "svg" / type / f"{name}.svg"
    body = path.read_text()

    # if type == "lucide":
    body = body.replace('width="24"', "")
    body = body.replace('height="24"', "")

    # body = body.replace('stroke="#0F172A"', "")
    # body = body.replace('fill="#0F172A"', "")

    if _class:
        kw["class"] = _class
    elif "class" in kw:
        kw["class"] = kw["class"]

    attrs_list = [
        # "stroke='currentColor'",
        # "fill='currentColor'",
    ]
    if kw:
        for attr_name, attr_value in kw.items():
            attr_name_kebab = attr_name.replace("_", "-")
            attrs_list.append(f"{attr_name_kebab}='{attr_value}'")

    attrs = " ".join(attrs_list)
    body = re.sub(r"<svg\s", f"<svg {attrs} ", body)

    body = f"<!-- icon: {type}/{name} -->\n{body}"
    return Markup(body)
