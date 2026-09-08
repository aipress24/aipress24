# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Bug #0333 — an obsolete profile value must stay saveable.

The rule the ticket settles on: accept the current taxonomy's values
**plus** the ones the profile already carried. Anything else is still
refused, so a retired term cannot be picked afresh.
"""

from __future__ import annotations

import pytest
from werkzeug.datastructures import MultiDict
from wtforms import Form

from app.modules.kyc.lib.retained_values import (
    RETAINED_GROUP,
    choice_values,
    retain_profile_values,
)
from app.modules.kyc.lib.select_multi_optgroup import SelectMultiOptgroupField
from app.modules.kyc.lib.select_multi_simple import SelectMultiSimpleField
from app.modules.kyc.lib.select_one import SelectOneField

CURRENT = [("Aéronautique", "Aéronautique"), ("Environnement", "Environnement")]
OBSOLETE = "Industrie lourde"

GROUPED = {
    "Industrie": [("Aéronautique", "Aéronautique")],
    "Nature": [("Environnement", "Environnement")],
}


def _form_with(field_class, choices, **kwargs):
    class F(Form):
        secteurs = field_class(choices=choices, **kwargs)

    return F


class TestChoiceValues:
    def test_reads_a_flat_list(self):
        assert choice_values(CURRENT) == {"Aéronautique", "Environnement"}

    def test_reads_an_optgroup_dict(self):
        assert choice_values(GROUPED) == {"Aéronautique", "Environnement"}

    def test_reads_bare_strings(self):
        assert choice_values(["Aéronautique"]) == {"Aéronautique"}

    def test_an_empty_list_offers_nothing(self):
        assert choice_values([]) == set()


class TestSingleSelect:
    def test_an_obsolete_value_is_refused_when_not_retained(self):
        """The behaviour the ticket reported: the member sees their
        value and cannot save."""
        form = _form_with(SelectOneField, CURRENT)(MultiDict({"secteurs": OBSOLETE}))

        assert not form.validate()

    def test_a_retained_value_validates(self):
        form = _form_with(SelectOneField, CURRENT)(MultiDict({"secteurs": OBSOLETE}))
        retain_profile_values(form, {"secteurs": OBSOLETE})

        assert form.validate(), form.errors

    def test_a_value_nobody_held_is_still_refused(self):
        form = _form_with(SelectOneField, CURRENT)(MultiDict({"secteurs": "Chimie"}))
        retain_profile_values(form, {"secteurs": OBSOLETE})

        assert not form.validate()


class TestMultiSelect:
    def test_a_retained_value_mixes_with_current_ones(self):
        form = _form_with(SelectMultiSimpleField, CURRENT)(
            MultiDict([("secteurs", OBSOLETE), ("secteurs", "Environnement")])
        )
        retain_profile_values(form, {"secteurs": [OBSOLETE]})

        assert form.validate(), form.errors
        assert set(form.secteurs.data) == {OBSOLETE, "Environnement"}

    def test_one_obsolete_value_does_not_open_the_others(self):
        form = _form_with(SelectMultiSimpleField, CURRENT)(
            MultiDict([("secteurs", OBSOLETE), ("secteurs", "Chimie")])
        )
        retain_profile_values(form, {"secteurs": [OBSOLETE]})

        assert not form.validate()

    def test_the_option_is_offered_so_the_widget_can_show_it(self):
        form = _form_with(SelectMultiSimpleField, CURRENT)()
        retain_profile_values(form, {"secteurs": [OBSOLETE]})

        assert OBSOLETE in choice_values(form.secteurs.choices)


class TestOptgroupSelect:
    def test_a_retained_value_lands_in_its_own_group(self):
        form = _form_with(SelectMultiOptgroupField, GROUPED)(
            MultiDict({"secteurs": OBSOLETE})
        )
        retain_profile_values(form, {"secteurs": [OBSOLETE]})

        assert form.validate(), form.errors
        assert choice_values(form.secteurs.choices[RETAINED_GROUP]) == {OBSOLETE}
        # The taxonomy's own groups are untouched.
        assert form.secteurs.choices["Industrie"] == GROUPED["Industrie"]


class TestWidening:
    def test_a_value_the_taxonomy_still_offers_adds_no_option(self):
        form = _form_with(SelectMultiSimpleField, CURRENT)()
        retain_profile_values(form, {"secteurs": ["Environnement"]})

        assert form.secteurs.choices == CURRENT

    def test_a_duplicated_value_is_offered_once(self):
        """A taxonomy merge can leave the same value twice on a profile;
        a duplicated option renders twice."""
        form = _form_with(SelectMultiSimpleField, CURRENT)()
        retain_profile_values(form, {"secteurs": [OBSOLETE, OBSOLETE]})

        assert form.secteurs.choices.count((OBSOLETE, OBSOLETE)) == 1

    @pytest.mark.parametrize("empty", [None, "", [], ["", "  "]])
    def test_nothing_held_widens_nothing(self, empty):
        form = _form_with(SelectMultiSimpleField, CURRENT)()
        retain_profile_values(form, {"secteurs": empty})

        assert form.secteurs.choices == CURRENT

    def test_a_field_that_does_not_retain_is_left_alone(self):
        """`retain_profile_values` walks the whole form — the free-text
        and dual selectors must not be touched."""

        class F(Form):
            secteurs = SelectMultiSimpleField(choices=CURRENT)

        form = F()
        retain_profile_values(form, {"inconnu": ["x"], "secteurs": [OBSOLETE]})

        assert OBSOLETE in choice_values(form.secteurs.choices)
