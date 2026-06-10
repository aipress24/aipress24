# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `app.flask.lib.wtforms.fields.base.BaseWidget`.

`BaseWidget.get_template` reads a `.j2` file colocated with the widget
module and renders it through `current_app.jinja_env`. Needs an app
context, which the a_unit autouse fixture provides.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Template

from app.flask.lib.wtforms.fields import base
from app.flask.lib.wtforms.fields.base import BaseWidget


class TestBaseWidgetGetTemplate:
    def test_returns_template_for_known_file(self) -> None:
        widget = BaseWidget()
        template = widget.get_template("rich_text.j2")
        assert isinstance(template, Template)

    def test_unknown_template_raises(self) -> None:
        widget = BaseWidget()
        with pytest.raises(FileNotFoundError):
            widget.get_template("does_not_exist.j2")

    def test_template_dir_is_colocated_with_module(self) -> None:
        # If a refactor moves the module, the template lookup breaks
        # silently — guard with a sanity check.
        module_dir = Path(base.__file__).parent
        assert (module_dir / "rich_text.j2").is_file()
        assert (module_dir / "rich_select.j2").is_file()
        assert (module_dir / "image.j2").is_file()
