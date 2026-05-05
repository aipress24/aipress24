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
        template = (self.SRC_ROOT / "modules" / "kyc" / "lib" / "country_select.j2").read_text()
        assert "col-span-12" not in template
        assert 'class="relative w-full"' in template
