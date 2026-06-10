# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `app.flask.lib.wtforms.renderer.FormRenderer`.

Why this file exists
--------------------
The `FormRenderer` is responsible for rendering WTForms forms into
Tailwind-styled HTML. It does so via a handful of Jinja2 templates and
a small set of pure helpers:

* `render_field_value`  — value-to-string formatting (None/bool/str/
  datetime/Arrow/default)
* `get_groups`          — pull the `Meta.groups` spec into a list of
  `{label, fields, id}` dicts
* `render_group`        — render a single group block
* `render_field`        — pick a CSS class from `FIELD_CLASS_MAP`,
  decide the template (view vs edit) and the value source (`field.data`
  for view-mode `media_id` / `publisher_id` ; the WTForms widget
  otherwise), render the field block
* `render`              — top-level entry point ; for `mode="view"`
  hits the view template, for `mode="edit"` hits the edit template

All tests below exercise these helpers WITHOUT mocks : we use plain
WTForms `Form` subclasses + tiny attrs-style stub objects that satisfy
the duck-typed attributes the renderer reads (`publisher.bw_name`,
`model.media.name`, `g.user.organisation`, ...).

The asserts check HTML output strings (or list shapes for
`get_groups`), never an internal interaction.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

import pytest
from arrow import Arrow
from flask import g
from markupsafe import Markup
from wtforms import DateField, DateTimeField, Form, SelectField, StringField

from app.flask.lib.wtforms.renderer import (
    DEFAULT_WIDTH,
    FIELD_CLASS_MAP,
    FormRenderer,
)

if TYPE_CHECKING:
    from flask import Flask


# ---------------------------------------------------------------------------
# Stubs (no mocks — duck-typed plain objects).
# ---------------------------------------------------------------------------


class _StubOrg:
    def __init__(self, name: str, bw_name: str | None = None) -> None:
        self.name = name
        self.bw_name = bw_name


class _StubMedia:
    def __init__(self, name: str) -> None:
        self.name = name


class _StubModel:
    """Duck-typed Event-like model with publisher + media + id."""

    def __init__(
        self,
        publisher: _StubOrg | None = None,
        media: _StubMedia | None = None,
        model_id: int = 42,
    ) -> None:
        self.id = model_id
        self.publisher = publisher
        self.media = media


class _StubUser:
    """Minimal user duck-typed for `FormRenderer.render` fallback path."""

    is_anonymous = False
    is_managing_another_bw = False
    selected_bw_id = None

    def __init__(self, organisation: _StubOrg | None = None) -> None:
        self.organisation = organisation


# ---------------------------------------------------------------------------
# Form fixtures.
# ---------------------------------------------------------------------------


class _SimpleForm(Form):
    class Meta:
        groups: ClassVar[dict] = {
            "main": {
                "label": "Main Info",
                "fields": ["name", "description"],
            },
            "extra": {
                "label": "",  # blank label — exercises the {% if group.label %} branch
                "fields": ["category"],
            },
        }

    name = StringField("Name", description="Your name")
    description = StringField("Description")
    category = SelectField("Category", choices=[("a", "A"), ("b", "B")])


class _FormWithDates(Form):
    class Meta:
        groups: ClassVar[dict] = {
            "dates": {
                "label": "Dates",
                "fields": ["birthday", "appointment"],
            },
        }

    birthday = DateField("Birthday")
    appointment = DateTimeField("Appointment")


class _FormWithMedia(Form):
    """Form including the `media_id` / `publisher_id` special-cased fields."""

    class Meta:
        groups: ClassVar[dict] = {
            "main": {
                "label": "Main",
                "fields": ["title", "media_id", "publisher_id"],
            },
        }

    title = StringField("Title")
    media_id = StringField("Media")
    publisher_id = StringField("Publisher")


class _FormWithRenderKw(Form):
    class Meta:
        groups: ClassVar[dict] = {
            "main": {"label": "Main", "fields": ["narrow"]},
        }

    narrow = StringField("Narrow", render_kw={"width": 3})


# ---------------------------------------------------------------------------
# Pure helper : render_field_value
# ---------------------------------------------------------------------------


class TestRenderFieldValue:
    """`render_field_value` is the only fully pure helper — match-case
    on the value type. Parametrize across all branches."""

    @pytest.fixture
    def renderer(self) -> FormRenderer:
        # The method does not touch self ; an empty form is enough.
        class _Empty(Form):
            class Meta:
                groups: ClassVar[dict] = {}

        return FormRenderer(form=_Empty(), model=None, mode="view")

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, ""),
            (True, "Oui"),
            (False, "Non"),
            ("hello", "hello"),
            ("", ""),
            (42, "42"),
            (3.14, "3.14"),
            ([1, 2], "[1, 2]"),
        ],
    )
    def test_render_field_value_scalars(
        self, renderer: FormRenderer, value, expected: str
    ):
        assert renderer.render_field_value(value) == expected

    def test_render_field_value_datetime(self, renderer: FormRenderer):
        # Naive datetime is intentional : the renderer uses strftime
        # only, no tz conversion. Format check is the contract.
        dt = datetime(2026, 6, 10, 14, 30)  # noqa: DTZ001
        assert renderer.render_field_value(dt) == "10/06/2026 à 14:30"

    def test_render_field_value_arrow(self, renderer: FormRenderer):
        arr = Arrow(2026, 1, 2, 9, 5)
        assert renderer.render_field_value(arr) == "02/01/2026 à 09:05"


# ---------------------------------------------------------------------------
# get_groups — pulls Meta.groups into a list of dicts with resolved fields.
# ---------------------------------------------------------------------------


class TestGetGroups:
    def test_empty_meta_groups_returns_empty_list(self):
        class _Empty(Form):
            class Meta:
                groups: ClassVar[dict] = {}

        renderer = FormRenderer(form=_Empty(), mode="edit")
        assert renderer.get_groups() == []

    def test_groups_have_id_label_and_resolved_field_objects(self):
        form = _SimpleForm()
        renderer = FormRenderer(form=form, mode="edit")

        groups = renderer.get_groups()

        assert [g["id"] for g in groups] == ["main", "extra"]
        assert [g["label"] for g in groups] == ["Main Info", ""]
        # Field objects come straight from the form, in the declared order.
        assert [f.name for f in groups[0]["fields"]] == ["name", "description"]
        assert [f.name for f in groups[1]["fields"]] == ["category"]
        # The original Meta.groups dict must not be mutated (it's copied).
        assert "id" not in form.Meta.groups["main"]
        assert form.Meta.groups["main"]["fields"] == ["name", "description"]

    def test_meta_groups_missing_defaults_to_empty(self):
        class _NoGroupsAttr(Form):
            class Meta:
                pass

            name = StringField("Name")

        renderer = FormRenderer(form=_NoGroupsAttr(), mode="edit")
        assert renderer.get_groups() == []


# ---------------------------------------------------------------------------
# render_group — small jinja wrapper, two templates (edit vs view).
# ---------------------------------------------------------------------------


class TestRenderGroup:
    def test_render_group_edit_mode_emits_label_and_fields(self, app: Flask):
        with app.app_context():
            form = _SimpleForm()
            renderer = FormRenderer(form=form, mode="edit")
            group = renderer.get_groups()[0]

            html = renderer.render_group(group)

        assert "Main Info" in html
        # Each field block must be rendered in the group's grid.
        assert html.count("sm:col-span-") == len(group["fields"])
        assert "grid grid-cols-1" in html

    def test_render_group_view_mode_uses_view_template(self, app: Flask):
        with app.app_context():
            form = _SimpleForm()
            renderer = FormRenderer(form=form, mode="view")
            group = renderer.get_groups()[0]

            html = renderer.render_group(group)

        # View template still includes label + grid structure.
        assert "Main Info" in html
        assert "sm:col-span-" in html

    def test_render_group_no_label_skips_h3(self, app: Flask):
        with app.app_context():
            form = _SimpleForm()
            renderer = FormRenderer(form=form, mode="edit")
            empty_label_group = renderer.get_groups()[1]

            html = renderer.render_group(empty_label_group)

        # Group "extra" has an empty label — no <h3> emitted.
        assert "<h3" not in html


# ---------------------------------------------------------------------------
# render_field — the meatiest method : class lookup, mode branching,
# render_kw width, special-cased field names in view mode.
# ---------------------------------------------------------------------------


class TestRenderFieldEditMode:
    def test_default_field_gets_default_class(self, app: Flask):
        with app.app_context():
            form = _SimpleForm()
            renderer = FormRenderer(form=form, mode="edit")

            html = renderer.render_field(form.name)

        assert FIELD_CLASS_MAP["default"] in html
        assert 'name="name"' in html
        # Default width injected on the wrapper div.
        assert f"sm:col-span-{DEFAULT_WIDTH}" in html

    def test_select_field_falls_through_to_default_class(self, app: Flask):
        """`SelectField` kebab-cases to "select-field" — NOT a key in
        FIELD_CLASS_MAP, so the renderer falls back to "default".
        Documents observed behaviour (the "select" / "date" / "date-time"
        entries in FIELD_CLASS_MAP are effectively dead today)."""
        with app.app_context():
            form = _SimpleForm()
            renderer = FormRenderer(form=form, mode="edit")

            html = renderer.render_field(form.category)

        assert FIELD_CLASS_MAP["default"] in html
        assert "<select" in html

    def test_date_field_falls_through_to_default_class(self, app: Flask):
        with app.app_context():
            form = _FormWithDates()
            renderer = FormRenderer(form=form, mode="edit")

            html = renderer.render_field(form.birthday)

        assert FIELD_CLASS_MAP["default"] in html

    def test_datetime_field_falls_through_to_default_class(self, app: Flask):
        with app.app_context():
            form = _FormWithDates()
            renderer = FormRenderer(form=form, mode="edit")

            html = renderer.render_field(form.appointment)

        assert FIELD_CLASS_MAP["default"] in html

    def test_field_with_errors_appends_input_error_class(self, app: Flask):
        with app.app_context():
            form = _SimpleForm()
            form.name.errors = ["Name is required"]
            renderer = FormRenderer(form=form, mode="edit")

            html = renderer.render_field(form.name)

        assert "input-error" in html
        # The first error must be surfaced.
        assert "Name is required" in html
        # Error-class wrapper around the label-text span.
        assert "text-red-500" in html

    def test_render_kw_width_overrides_default(self, app: Flask):
        with app.app_context():
            form = _FormWithRenderKw()
            renderer = FormRenderer(form=form, mode="edit")

            html = renderer.render_field(form.narrow)

        assert "sm:col-span-3" in html
        assert f"sm:col-span-{DEFAULT_WIDTH}" not in html

    def test_field_description_surfaces_under_field(self, app: Flask):
        with app.app_context():
            form = _SimpleForm()
            renderer = FormRenderer(form=form, mode="edit")

            html = renderer.render_field(form.name)

        assert "Your name" in html

    def test_country_select_field_uses_default_class_branch(self, app: Flask):
        """`CountrySelectField` kebab-cases to "country-select-field" —
        the renderer special-cases this name to (a) use the default
        class and (b) place the raw `field` object (not its rendered
        widget) into the template context. We exercise (a) here by
        defining a class with the matching name and a no-op widget,
        bypassing the full kyc.country_select Jinja machinery."""

        def _noop_widget(field, **kwargs):
            return Markup("<country-widget/>")

        # Local subclass whose name is what the renderer checks for.
        class CountrySelectField(SelectField):
            widget = staticmethod(_noop_widget)

        class _CountryForm(Form):
            class Meta:
                groups: ClassVar[dict] = {
                    "main": {"label": "Main", "fields": ["country"]},
                }

            country = CountrySelectField("Country", choices=[("fr", "France")])

        with app.app_context():
            form = _CountryForm()
            renderer = FormRenderer(form=form, mode="edit")

            html = renderer.render_field(form.country)

        # The "country-select-field" branch puts the raw `field`
        # (NOT `field(**{"class": class_})`) into the template ; the
        # widget output we stubbed is what should appear.
        assert "<country-widget/>" in html
        # Label / wrapper still emitted ; default width still applied.
        assert "Country" in html
        assert f"sm:col-span-{DEFAULT_WIDTH}" in html


class TestRenderFieldViewMode:
    def test_view_mode_default_field_renders_value_not_input(self, app: Flask):
        with app.app_context():
            form = _SimpleForm()
            form.name.data = "Alice"
            renderer = FormRenderer(form=form, mode="view")

            html = renderer.render_field(form.name)

        assert "Alice" in html
        # In view mode the raw widget is NOT rendered — `field.data` is.
        assert "<input" not in html

    def test_view_mode_media_id_with_model_media_shows_media_name(self, app: Flask):
        with app.app_context():
            form = _FormWithMedia()
            model = _StubModel(media=_StubMedia(name="Hero Image"))
            renderer = FormRenderer(form=form, model=model, mode="view")

            html = renderer.render_field(form.media_id)

        assert "Hero Image" in html

    def test_view_mode_media_id_without_model_renders_empty_value(self, app: Flask):
        with app.app_context():
            form = _FormWithMedia()
            renderer = FormRenderer(form=form, model=None, mode="view")

            html = renderer.render_field(form.media_id)

        # Label is still emitted, but no media name.
        assert "Media" in html
        assert "Hero Image" not in html

    def test_view_mode_publisher_id_renders_publisher_bw_name(self, app: Flask):
        with app.app_context():
            form = _FormWithMedia()
            org = _StubOrg(name="Acme Press", bw_name="Acme BW")
            model = _StubModel(publisher=org)
            renderer = FormRenderer(form=form, model=model, mode="view")

            html = renderer.render_field(form.publisher_id)

        assert "Acme BW" in html
        # bw_name wins over .name when both present.
        assert "Acme Press" not in html

    def test_view_mode_publisher_id_falls_back_to_org_name(self, app: Flask):
        with app.app_context():
            form = _FormWithMedia()
            org = _StubOrg(name="Acme Press")  # no bw_name
            model = _StubModel(publisher=org)
            renderer = FormRenderer(form=form, model=model, mode="view")

            html = renderer.render_field(form.publisher_id)

        assert "Acme Press" in html

    def test_view_mode_publisher_id_no_publisher_yields_empty(self, app: Flask):
        with app.app_context():
            form = _FormWithMedia()
            model = _StubModel(publisher=None)
            renderer = FormRenderer(form=form, model=model, mode="view")

            html = renderer.render_field(form.publisher_id)

        # Label still present, but no publisher name leaks.
        assert "Publisher" in html
        assert "Acme" not in html


# ---------------------------------------------------------------------------
# render — top-level template selection. The publisher_text branch is
# already covered by tests/a_unit/flask/lib/test_wtforms_renderer.py ;
# here we focus on view-mode rendering + an empty Meta.groups form.
# ---------------------------------------------------------------------------


class TestRender:
    def test_render_view_mode_emits_view_form_shell(self, app: Flask):
        with app.test_request_context("/x"):
            g.user = _StubUser(organisation=_StubOrg(name="Org"))
            renderer = FormRenderer(
                form=_SimpleForm(),
                model=_StubModel(),
                mode="view",
            )
            html = str(renderer.render())

        # The view template uses an anchor "Retour" instead of submit buttons.
        assert "Retour" in html
        assert "_action" not in html
        assert "Annuler" not in html

    def test_render_edit_mode_emits_action_url_and_buttons(self, app: Flask):
        with app.test_request_context("/y"):
            g.user = _StubUser(organisation=_StubOrg(name="Org"))
            renderer = FormRenderer(
                form=_SimpleForm(),
                model=_StubModel(),
                mode="edit",
                action_url="/save",
            )
            html = str(renderer.render())

        assert 'action="/save"' in html
        assert "Annuler" in html
        assert "Enregistrer" in html
        # Hidden id input is emitted when a model is present.
        assert 'name="id"' in html

    def test_render_edit_no_model_skips_hidden_id_input(self, app: Flask):
        with app.test_request_context("/z"):
            g.user = _StubUser(organisation=_StubOrg(name="Org"))
            renderer = FormRenderer(
                form=_SimpleForm(),
                model=None,
                mode="edit",
                action_url="/save",
            )
            html = str(renderer.render())

        assert 'name="id"' not in html
        # Form shell still present.
        assert 'action="/save"' in html
