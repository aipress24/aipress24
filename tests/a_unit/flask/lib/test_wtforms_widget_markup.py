# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Autoescape-class guard for the flask wtforms widgets.

Family of bug #0162 / H1 / #0126: a widget that returns a bare `str`
from `jinja2.Template.render()` is HTML-escaped at the call site under
the `.j2` autoescape policy, so the widget shows up as literal text
(it bit the biz market forms via the country widget). The contract is
that a widget MUST return `markupsafe.Markup`. These widgets are
currently safe *only* because the generic `FormRenderer` happens to
wrap field output in `Markup` (`renderer.py:262`); a direct
`{{ form.x() }}` (as the biz forms did) bypasses that. Pin the
contract at the source so a new/edited widget can't silently
reintroduce the escaped-literal bug.
"""

from __future__ import annotations

from pathlib import Path


def test_every_flask_wtforms_widget_wraps_render_in_markup() -> None:
    fields_dir = (
        Path(__file__).resolve().parents[4]
        / "src/app/flask/lib/wtforms/fields"
    )
    assert fields_dir.is_dir(), fields_dir

    offenders: list[str] = []
    for py in sorted(fields_dir.glob("*.py")):
        for lineno, line in enumerate(
            py.read_text(encoding="utf-8").splitlines(), 1
        ):
            stripped = line.strip()
            if not stripped.startswith("return "):
                continue
            if ".render(" not in stripped:
                continue
            if "Markup(" not in stripped:
                offenders.append(f"{py.name}:{lineno}: {stripped}")

    assert not offenders, (
        "flask wtforms widget(s) return a bare str from "
        "template.render() — must wrap in markupsafe.Markup or the "
        "widget renders as escaped literal text when used directly "
        "in a .j2 template (autoescape family, #0162):\n"
        + "\n".join(offenders)
    )
