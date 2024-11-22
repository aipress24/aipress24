# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from pathlib import Path

from flask import current_app
from jinja2 import Template


class BaseWidget:
    def get_template(self, name: str) -> Template:
        template_path = Path(__file__).parent / name
        return current_app.jinja_env.from_string(template_path.read_text())
