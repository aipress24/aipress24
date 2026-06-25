# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `MissionOfferForm` validation in
`app.modules.biz.views.missions`.

WTForms validation runs in-process — no DB, no HTTP — so it lands
naturally in a_unit. Pinning the validators here catches three
classes of silent regression :

1. **Tightening** : a future « add length max to description » that
   breaks legitimate long-form descriptions.
2. **Loosening** : a future « accidentally remove InputRequired »
   that lets blank missions ship to PUBLIC.
3. **Field rename** : POST data that the form silently doesn't see
   because the field name changed without the publish-form template
   being updated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from werkzeug.datastructures import ImmutableMultiDict

from app.modules.biz.views.missions import MissionOfferForm

if TYPE_CHECKING:
    from flask import Flask


def _make_form(app: Flask, data: dict | None = None) -> MissionOfferForm:
    """Instantiate `MissionOfferForm` against a fake POST payload.
    Used by every test below — encapsulates the test_request_context +
    ImmutableMultiDict wrapping that WTForms expects."""
    payload = ImmutableMultiDict(data or {})
    with app.test_request_context():
        return MissionOfferForm(payload)


class TestTitleField:
    def test_required(self, app: Flask):
        """Empty title → invalid. The publish form must not allow a
        nameless offer to land in the listings."""
        form = _make_form(app, {"description": "x" * 30})
        assert not form.validate()
        assert form.title.errors

    def test_accepts_typical_title(self, app: Flask):
        form = _make_form(
            app,
            {"title": "Rédacteur·rice tech", "description": "x" * 30},
        )
        # Title alone is OK ; we ignore description errors here.
        form.validate()
        assert not form.title.errors

    def test_max_length_200(self, app: Flask):
        """Pin the upper bound. A 201-char title fails ; 200 chars OK.
        Catches a future « bump to 500 » that's at odds with the DB
        column."""
        form_long = _make_form(
            app,
            {"title": "x" * 201, "description": "x" * 30},
        )
        assert not form_long.validate()
        assert form_long.title.errors

        form_exact = _make_form(
            app,
            {"title": "x" * 200, "description": "x" * 30},
        )
        form_exact.validate()
        assert not form_exact.title.errors


class TestDescriptionField:
    def test_required(self, app: Flask):
        form = _make_form(app, {"title": "Mission"})
        assert not form.validate()
        assert form.description.errors

    def test_min_length_20(self, app: Flask):
        """Erick's rule : a meaningful description is at least 20
        characters. A short « TBD » must fail."""
        form = _make_form(app, {"title": "M", "description": "too short"})
        assert not form.validate()
        assert form.description.errors

    def test_accepts_20_chars_exactly(self, app: Flask):
        """The boundary itself. 20 chars OK ; 19 fails. Catches a
        future « bump min to 50 » that would invalidate seed data."""
        form = _make_form(app, {"title": "M", "description": "x" * 20})
        form.validate()
        assert not form.description.errors

    def test_no_upper_bound(self, app: Flask):
        """Long descriptions are fine — pin so a future « max 500 »
        addition doesn't silently reject legitimate long-form
        descriptions."""
        form = _make_form(app, {"title": "M", "description": "x" * 5000})
        form.validate()
        assert not form.description.errors


class TestOptionalFields:
    """All non-title / non-description / non-category fields are optional.
    Pin that contract so a future « accidentally added InputRequired » is
    caught — empty sector / location / budget should pass."""

    def test_all_optionals_empty_passes(self, app: Flask):
        """A minimal valid form has title + description + category. Every
        other field empty must not fail validation."""
        form = _make_form(
            app,
            {
                "title": "Mission",
                "description": "x" * 30,
                "category": "journalisme",
            },
        )
        assert form.validate()

    def test_sector_optional(self, app: Flask):
        form = _make_form(
            app,
            {"title": "M", "description": "x" * 30, "sector": ""},
        )
        form.validate()
        assert not form.sector.errors

    def test_budget_min_optional(self, app: Flask):
        form = _make_form(
            app,
            {"title": "M", "description": "x" * 30, "budget_min": ""},
        )
        form.validate()
        assert not form.budget_min.errors

    def test_budget_max_optional(self, app: Flask):
        form = _make_form(
            app,
            {"title": "M", "description": "x" * 30, "budget_max": ""},
        )
        form.validate()
        assert not form.budget_max.errors

    def test_deadline_optional(self, app: Flask):
        form = _make_form(
            app,
            {"title": "M", "description": "x" * 30, "deadline": ""},
        )
        form.validate()
        assert not form.deadline.errors

    def test_category_required(self, app: Flask):
        """Bug #0224: category is required. An empty category must fail
        validation so blank missions can't be created."""
        form = _make_form(
            app,
            {"title": "M", "description": "x" * 30, "category": ""},
        )
        assert not form.validate()
        assert form.category.errors

    def test_subcategory_max_200(self, app: Flask):
        """The free-text subcategory has a 200-char ceiling matching
        the DB column. Pin so a future « max 1000 » doesn't break
        the column constraint at insert time."""
        form = _make_form(
            app,
            {
                "title": "M",
                "description": "x" * 30,
                "subcategory": "x" * 201,
            },
        )
        assert not form.validate()
        assert form.subcategory.errors


class TestCategoryValidation:
    """The `category` field is a SelectField over `_CATEGORY_CHOICES`.
    WTForms enforces « value must be one of the choices » by default.
    Pin the strict policy so a future `validate_choice=False`
    regression that lets bogus values reach the DB is caught."""

    def test_unrecognised_category_value_rejected(self, app: Flask):
        form = _make_form(
            app,
            {
                "title": "M",
                "description": "x" * 30,
                "category": "totally-bogus",
            },
        )
        assert not form.validate()
        assert form.category.errors

    def test_blank_category_rejected(self, app: Flask):
        """Bug #0224: the blank placeholder choice is not a valid value.
        A mission must have a real category."""
        form = _make_form(
            app,
            {
                "title": "M",
                "description": "x" * 30,
                "category": "",
            },
        )
        assert not form.validate()
        assert form.category.errors

    def test_canonical_categories_accepted(self, app: Flask):
        """Each of the three official categories must pass."""
        for cat in ("journalisme", "communication", "innovation"):
            form = _make_form(
                app,
                {
                    "title": "M",
                    "description": "x" * 30,
                    "category": cat,
                },
            )
            assert form.validate(), (
                f"Category {cat!r} should be accepted, errors: {form.errors}"
            )


class TestBooleanFields:
    """`physical_required` and `remote_required` default to False
    when the checkbox is unchecked. Pin so a future « default True »
    regression doesn't silently flip every new mission."""

    def test_physical_required_defaults_to_false(self, app: Flask):
        form = _make_form(app, {"title": "M", "description": "x" * 30})
        # `data` is what `db_session.add(MissionOffer(...))` reads.
        assert form.physical_required.data is False

    def test_remote_required_defaults_to_false(self, app: Flask):
        form = _make_form(app, {"title": "M", "description": "x" * 30})
        assert form.remote_required.data is False

    def test_checkbox_value_yields_true(self, app: Flask):
        """When the browser POSTs `physical_required=y` (default for
        HTML checkboxes), WTForms coerces to True. Pin so a future
        change to a different on-value (e.g. "1") doesn't silently
        store unchecked rows as checked."""
        form = _make_form(
            app,
            {
                "title": "M",
                "description": "x" * 30,
                "physical_required": "y",
            },
        )
        assert form.physical_required.data is True
