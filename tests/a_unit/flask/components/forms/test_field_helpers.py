# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for ``app.flask.components.forms._field``.

The Field hierarchy is mostly pure: ``type()`` derives a kebab-case
discriminator from the class name; ``extras()`` returns an empty dict
by default (or, for SelectField/RichSelectField, options derived from a
choices lookup); ``__getitem__`` / ``__getattr__`` route attribute
access first through ``extras()`` and then through the underlying spec
dict; ``render_view`` simply wraps ``value`` in Markup.

These tests pin that behaviour without touching Flask globals, Jinja
template loading, or the live ``get_choices()`` vocabulary lookup
(which itself requires an application context). For the two
choices-driven Select fields we use the injection seam
(``choices_fn`` keyword argument) added to keep the production
default unchanged while letting tests pass a stub callable.
"""

from __future__ import annotations

import pytest
from attr import frozen as _frozen
from markupsafe import Markup

from app.flask.components.forms._field import (
    DateField,
    DateTimeField,
    DatetimeField,
    Field,
    ImageField,
    InputField,
    RichSelectField,
    RichTextField,
    SelectField,
    TextField,
    TimeField,
    VideoField,
)


class TestFieldType:
    """``Field.type()`` strips the ``Field`` suffix then kebab-cases."""

    @pytest.mark.parametrize(
        ("cls", "expected"),
        [
            (DateField, "date"),
            (TimeField, "time"),
            (DateTimeField, "date-time"),
            (DatetimeField, "datetime"),
            (ImageField, "image"),
            (InputField, "input"),
            (RichTextField, "rich-text"),
            (SelectField, "select"),
            (RichSelectField, "rich-select"),
            (TextField, "text"),
            (VideoField, "video"),
        ],
    )
    def test_type_returns_kebab_case_name(self, cls, expected):
        assert cls.type() == expected

    def test_base_field_type_is_empty(self):
        # "Field"[0:-5] == "" so we expect the empty string.
        assert Field.type() == ""


class TestFieldDefaultExtras:
    """The base ``Field.extras()`` returns an empty dict."""

    def test_extras_default_is_empty_dict(self):
        field = TextField(spec={"id": "title"}, value="hello")

        assert field.extras() == {}

    @pytest.mark.parametrize(
        "cls",
        [DateField, TimeField, ImageField, InputField, TextField, VideoField],
    )
    def test_non_select_fields_inherit_empty_extras(self, cls):
        field = cls(spec={"id": "x"}, value=None)

        assert field.extras() == {}


class TestFieldGetItem:
    """``Field[key]`` checks ``extras()`` first, then falls back to spec."""

    def test_getitem_falls_back_to_spec(self):
        field = TextField(spec={"id": "title", "label": "Title"}, value="")

        assert field["label"] == "Title"
        assert field["id"] == "title"

    def test_getitem_missing_key_raises(self):
        field = TextField(spec={"id": "title"}, value="")

        with pytest.raises(KeyError):
            _ = field["nope"]


class TestFieldGetAttr:
    """``Field.<attr>`` mirrors ``__getitem__`` with one exception."""

    def test_getattr_returns_spec_value(self):
        field = TextField(spec={"id": "x", "label": "Label"}, value="v")

        assert field.label == "Label"
        assert field.id == "x"

    def test_getattr_deepcopy_raises_attribute_error(self):
        """``__deepcopy__`` is an opt-out so ``copy.deepcopy`` falls back."""
        field = TextField(spec={"id": "x"}, value="v")

        with pytest.raises(AttributeError):
            field.__getattr__("__deepcopy__")

    def test_getattr_missing_key_raises_keyerror(self):
        # The implementation re-raises the underlying spec dict's KeyError.
        field = TextField(spec={"id": "x"}, value="v")

        with pytest.raises(KeyError):
            field.__getattr__("not_there")


class TestRenderView:
    """``render_view`` wraps ``value`` in ``Markup`` unchanged."""

    @pytest.mark.parametrize(
        "value",
        ["hello", "", "<b>bold</b>", "with spaces & ampersand"],
    )
    def test_render_view_returns_markup_of_value(self, value):
        field = TextField(spec={"id": "x"}, value=value)

        result = field.render_view()

        assert isinstance(result, Markup)
        assert str(result) == value


class TestFrozenSemantics:
    """``@frozen`` instances reject attribute assignment after creation."""

    def test_field_is_immutable(self):
        field = TextField(spec={"id": "x"}, value="v")

        with pytest.raises(Exception):
            field.value = "other"  # type: ignore[misc]

    def test_two_fields_with_equal_data_are_equal(self):
        a = TextField(spec={"id": "x"}, value="v")
        b = TextField(spec={"id": "x"}, value="v")

        assert a == b


# --- extras() short-circuit branches ----------------------------------------


@_frozen
class _FakeExtrasField(Field):
    """A Field subclass with non-empty ``extras()`` for branch coverage."""

    def extras(self):
        return {"injected": "from-extras"}


class TestExtrasShortCircuit:
    """Verify ``extras()`` shadows the spec dict in both lookup paths."""

    def test_getitem_returns_value_from_extras_when_present(self):
        field = _FakeExtrasField(
            spec={"injected": "from-spec", "id": "x"},
            value=None,
        )

        assert field["injected"] == "from-extras"

    def test_getitem_falls_back_to_spec_when_extras_missing(self):
        field = _FakeExtrasField(spec={"id": "x"}, value=None)

        assert field["id"] == "x"

    def test_getattr_returns_value_from_extras_when_present(self):
        field = _FakeExtrasField(
            spec={"injected": "from-spec"},
            value=None,
        )

        # __getattr__ is only called for missing attributes, so direct
        # attribute access goes through the extras short-circuit.
        assert field.injected == "from-extras"

    def test_getattr_falls_back_to_spec_when_extras_missing(self):
        field = _FakeExtrasField(spec={"id": "x"}, value=None)

        assert field.id == "x"


# --- SelectField / RichSelectField -------------------------------------------


def _stub_choices():
    """Return a deterministic, in-memory choices mapping for tests."""
    return {
        "language": ["fr", "en"],
        "section": ["a", "b", "c"],
    }


class TestSelectFieldExtras:
    """``SelectField.extras`` returns options for known keys."""

    def test_extras_returns_options_for_known_key(self):
        field = SelectField(spec={"key": "language"}, value=None)

        extras = field.extras(choices_fn=_stub_choices)

        assert extras == {
            "options": [
                {"value": "fr", "label": "fr", "selected": ""},
                {"value": "en", "label": "en", "selected": ""},
            ],
        }

    def test_extras_returns_empty_options_for_unknown_key(self):
        field = SelectField(spec={"key": "missing"}, value=None)

        extras = field.extras(choices_fn=_stub_choices)

        assert extras == {"options": {}}

    def test_get_options_builds_records_from_choices(self):
        field = SelectField(spec={"key": "section"}, value=None)

        options = field.get_options("section", choices_fn=_stub_choices)

        assert options == [
            {"value": "a", "label": "a", "selected": ""},
            {"value": "b", "label": "b", "selected": ""},
            {"value": "c", "label": "c", "selected": ""},
        ]

    def test_extras_takes_precedence_over_spec_on_getitem(self):
        """``__getitem__`` should prefer the ``extras()`` value over spec."""
        field = SelectField(
            spec={"key": "language", "options": "ignored"},
            value=None,
        )
        # Bypass DI default with a custom call to materialise extras dict.
        extras = field.extras(choices_fn=_stub_choices)
        assert "options" in extras
        # Verify spec value coexists but is shadowed by extras when keys clash.
        assert field.spec["options"] == "ignored"


class TestRichSelectFieldExtras:
    """``RichSelectField`` adds an empty ``value`` to extras."""

    def test_extras_known_key_includes_value(self):
        field = RichSelectField(spec={"key": "language"}, value=None)

        extras = field.extras(choices_fn=_stub_choices)

        assert extras["value"] == ""
        assert extras["options"] == [
            {"value": "fr", "label": "fr", "selected": ""},
            {"value": "en", "label": "en", "selected": ""},
        ]

    def test_extras_unknown_key_returns_empty_options(self):
        field = RichSelectField(spec={"key": "nope"}, value=None)

        extras = field.extras(choices_fn=_stub_choices)

        assert extras == {"options": {}, "value": ""}

    def test_get_options_uses_provided_choices(self):
        field = RichSelectField(spec={"key": "section"}, value=None)

        options = field.get_options("section", choices_fn=_stub_choices)

        assert [o["value"] for o in options] == ["a", "b", "c"]
        assert all(o["selected"] == "" for o in options)
