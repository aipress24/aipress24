# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`DisplayField` shows a derived value and never writes one back."""

from __future__ import annotations

from types import SimpleNamespace

from werkzeug.datastructures import MultiDict
from wtforms import Form

from app.flask.lib.wtforms.fields import DisplayField


class _Form(Form):
    addressed_to = DisplayField("Commande adressée à")
    commanditaire = DisplayField(
        "Commanditaire", formatter=lambda user: user.full_name if user else ""
    )


def test_it_shows_the_value_it_was_given():
    form = _Form(obj=SimpleNamespace(addressed_to="Aïcha", commanditaire=None))

    assert form.addressed_to._value() == "Aïcha"


def test_the_formatter_turns_an_object_into_its_label():
    form = _Form(
        obj=SimpleNamespace(
            addressed_to="", commanditaire=SimpleNamespace(full_name="Eliane Kan")
        )
    )

    assert form.commanditaire._value() == "Eliane Kan"


def test_populate_obj_writes_nothing():
    """`addressed_to` is a property with no setter: writing back would
    raise, and that is the whole reason this field exists."""
    form = _Form(obj=SimpleNamespace(addressed_to="Aïcha", commanditaire=None))
    target = SimpleNamespace()

    form.addressed_to.populate_obj(target, "addressed_to")

    assert not hasattr(target, "addressed_to")


def test_a_normal_post_leaves_the_value_alone():
    """No `<input>` is rendered, so a submitted form carries no key for
    this field and the object's value survives the round trip."""
    form = _Form(
        MultiDict({"titre": "inchangé"}),
        obj=SimpleNamespace(addressed_to="Aïcha", commanditaire=None),
    )

    assert form.addressed_to._value() == "Aïcha"


def test_it_renders_no_input_and_escapes_its_value():
    form = _Form(obj=SimpleNamespace(addressed_to="<script>x</script>", commanditaire=None))

    html = str(form.addressed_to())

    assert "<input" not in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
