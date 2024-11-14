# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import inspect
from pathlib import Path

from flask import current_app
from jinja2 import Environment, Template

from app.lib.names import to_snake_case


def get_template(cls: type) -> Template:
    template_name = to_snake_case(cls.__name__) + ".j2"
    template_file = Path(inspect.getfile(cls)).parent / template_name
    jinja_env: Environment = current_app.jinja_env
    return jinja_env.from_string(template_file.read_text())
