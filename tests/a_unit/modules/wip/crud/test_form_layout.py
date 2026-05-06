# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression tests for bug 0124-A: "Pays" field overlaps "Publier pour" when its
Choices.js dropdown panel is opened.

Root cause: in the metadata group of CommuniqueForm, `publisher_id` was rendered
BEFORE `pays_zip_ville`. The Choices.js dropdown panel of `publisher_id` extends
downward and was being visually masked by the CountrySelectField's tom-select
widget rendered just below it. Fix: render `publisher_id` LAST in the metadata
group so its dropdown opens into the gap before the next group.

The widget templates also carried a dead `col-span-12 w-full` class that has no
effect outside a CSS grid; that has been replaced with `relative w-full` to
establish a clean stacking context for any absolute-positioned dropdown panel.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.flask.lib.wtforms.renderer import (
    FIELD_TEMPLATE,
    FIELD_VIEW_TEMPLATE,
    FormRenderer,
)
from app.modules.wip.crud.cbvs._forms import CommuniqueForm, EventForm


class TestPublisherIdRenderedLast:
    """Bug 0124-A: publisher_id must render after pays_zip_ville to avoid
    Choices.js dropdown being masked by the country select widget below it."""

    def test_communique_form_publisher_id_after_pays_zip_ville(self):
        fields = CommuniqueForm.Meta.groups["metadata"]["fields"]
        assert "publisher_id" in fields
        assert "pays_zip_ville" in fields
        assert fields.index("publisher_id") > fields.index("pays_zip_ville"), (
            "publisher_id must render AFTER pays_zip_ville so its dropdown "
            "doesn't get masked by the country select widget below."
        )

    def test_communique_form_publisher_id_is_last_in_metadata_group(self):
        fields = CommuniqueForm.Meta.groups["metadata"]["fields"]
        assert fields[-1] == "publisher_id"

    def test_event_form_publisher_id_is_last_in_metadata_group(self):
        """EventForm already had publisher_id last; lock that in."""
        fields = EventForm.Meta.groups["metadata"]["fields"]
        assert fields[-1] == "publisher_id"


class TestPublisherIdHelpText:
    """Bug 0124-C: clarify that the CP/event appears on the agency's BW too,
    and in NEWS / Idées & Comm', without requiring a multi-select. The fix is
    a help-text rendered under the "Publier pour" select."""

    def test_communique_form_publisher_id_has_description(self):
        form = CommuniqueForm()
        assert form.publisher_id.description, (
            "publisher_id must carry a description explaining the dual-BW + "
            "NEWS visibility behavior."
        )
        # Spot-check the wording covers the three destinations.
        text = form.publisher_id.description
        assert (
            "agence" in text
            or "votre propre organisation" in text.lower()
            or ("votre" in text.lower() and "bw" in text.lower())
        )
        assert "NEWS" in text or "Idées" in text or "Comm" in text

    def test_event_form_publisher_id_has_description(self):
        form = EventForm()
        assert form.publisher_id.description, (
            "EventForm.publisher_id must carry the same help-text."
        )

    def test_renderer_surfaces_description_in_html(self):
        """The renderer's FIELD_TEMPLATE must render `field.description` so the
        text actually reaches the page."""
        assert "{{ description }}" in FIELD_TEMPLATE
        assert "{{ description }}" in FIELD_VIEW_TEMPLATE


class TestPublisherIdRenderedAsName:
    """Bug 0129: in view ("Voir") mode, the publisher_id field must show the
    organisation name, not the raw FK id."""

    def _render_publisher_field(self, app, form_cls, publisher):
        form = form_cls()
        form.publisher_id.data = (
            getattr(publisher, "id", None) if publisher is not None else None
        )
        model = SimpleNamespace(id=1, publisher=publisher, media=None)
        renderer = FormRenderer(form=form, model=model, mode="view")
        with app.test_request_context():
            return renderer.render_field(form.publisher_id)

    def test_communique_view_renders_publisher_bw_name(self, app):
        publisher = SimpleNamespace(id=42, name="Fake-Léonard", bw_name="Léonard SA")
        html = self._render_publisher_field(app, CommuniqueForm, publisher)
        assert "Léonard SA" in html
        assert "42" not in html, (
            f"raw publisher id leaked into the rendered view: {html!r}"
        )

    def test_event_view_renders_publisher_bw_name(self, app):
        publisher = SimpleNamespace(id=999, name="Fake-Org", bw_name="My BW")
        html = self._render_publisher_field(app, EventForm, publisher)
        assert "My BW" in html
        assert "999" not in html

    def test_falls_back_to_name_when_bw_name_empty(self, app):
        publisher = SimpleNamespace(id=7, name="OnlyName", bw_name="")
        html = self._render_publisher_field(app, CommuniqueForm, publisher)
        assert "OnlyName" in html
        assert "7" not in html.replace("<", " <").split(">")[0]  # not in tag soup

    def test_renders_empty_when_publisher_missing(self, app):
        html = self._render_publisher_field(app, CommuniqueForm, publisher=None)
        # Don't dump a raw int even if the form data carried one.
        assert ">None<" not in html
        # The label "Publier pour" remains; the value section is empty.
        assert "Publier pour" in html


class TestWidgetTemplateStackingContext:
    """The rich_select and country_select widget templates used to hardcode
    `col-span-12 w-full` on a non-grid child, which is dead CSS but fragile.
    Replaced with `relative w-full` to give absolute-positioned dropdowns a
    proper stacking context."""

    SRC_ROOT = Path(__file__).parents[5] / "src" / "app"

    def test_rich_select_template_no_dead_grid_classes(self):
        template = (
            self.SRC_ROOT / "flask" / "lib" / "wtforms" / "fields" / "rich_select.j2"
        ).read_text()
        assert "col-span-12" not in template, (
            "rich_select widget should not carry col-span-12 (dead outside a grid)."
        )
        assert 'class="relative w-full"' in template

    def test_country_select_template_no_dead_grid_classes(self):
        template = (
            self.SRC_ROOT / "modules" / "kyc" / "lib" / "country_select.j2"
        ).read_text()
        assert "col-span-12" not in template
        assert 'class="relative w-full"' in template
