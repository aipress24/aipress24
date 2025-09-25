"""Base widget class for WTForms custom field widgets."""

# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from pathlib import Path

from flask import current_app
from jinja2 import Template


class BaseWidget:
    """Base widget class for custom WTForms field rendering."""

    def get_template(self, name: str) -> Template:
        """Load and return a Jinja2 template from the local template directory."""
        template_path = Path(__file__).parent / name
        return current_app.jinja_env.from_string(template_path.read_text())
