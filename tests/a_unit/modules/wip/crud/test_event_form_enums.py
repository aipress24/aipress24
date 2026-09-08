# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The form is the boundary where `mode` and `pricing` become enums.

Production bug: the select carried `EventMode.name` ("ON_SITE") while
the `StrEnum`'s own value is "on_site". `populate_obj` wrote that raw
name onto the model, and `REQUIRED_BY_MODE["ON_SITE"]` raised
`KeyError` mid-publication. Pinning the round trip here is what keeps
the coercion out of the model and off every read site.
"""

from __future__ import annotations

from werkzeug.datastructures import MultiDict

from app.enums import EventMode, EventPricing
from app.modules.wip.crud.cbvs._forms import EventForm


def _form(**data) -> EventForm:
    return EventForm(MultiDict(data))


class _Target:
    mode = None
    pricing = None


def test_submitted_values_reach_the_model_as_enums():
    form = _form(mode="online", pricing="paid")
    target = _Target()
    form.mode.populate_obj(target, "mode")
    form.pricing.populate_obj(target, "pricing")

    assert target.mode is EventMode.ONLINE
    assert target.pricing is EventPricing.PAID


def test_an_existing_event_preselects_its_own_option():
    """`EventForm(obj=event)` hands the field an enum, not a string."""

    class Event:
        mode = EventMode.HYBRID
        pricing = EventPricing.FREE_FOR_JOURNALISTS

    form = EventForm(obj=Event())
    selected = [value for value, _, sel, *_ in form.mode.iter_choices() if sel]

    assert selected == [EventMode.HYBRID]


def test_a_tampered_value_is_a_form_error_not_a_crash():
    form = _form(mode="garbage")

    assert not form.validate()
    assert form.mode.errors


def test_defaults_are_enums():
    form = EventForm()

    assert form.mode.data is EventMode.ON_SITE
    assert form.pricing.data is EventPricing.FREE_FOR_ALL
