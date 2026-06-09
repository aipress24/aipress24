# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `_get_tabs()` in `app.modules.biz.views.home`.

`_get_tabs()` reads `request.args["current_tab"]` and returns a list
of dicts the template iterates to build the MARKET tab strip. Each
dict has :

- `id`     — matches the entry in `TABS`
- `label`  — user-facing French label
- `href`   — URL built with `url_for(".biz", current_tab=…)`
- `current` — bool, true for the active tab

Pin so a future refactor that drops one of these keys silently
empties a section of the tab strip.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.biz.models import ContractType
from app.modules.biz.views._common import TABS
from app.modules.biz.views.home import _get_tabs
from app.modules.biz.views.jobs import _CONTRACT_CHOICES

if TYPE_CHECKING:
    from flask import Flask


class TestGetTabs:
    def test_returns_one_dict_per_tabs_entry(self, app: Flask):
        with app.test_request_context("/biz/"):
            result = _get_tabs()
        assert len(result) == len(TABS)

    def test_every_dict_has_id_label_href_current(self, app: Flask):
        with app.test_request_context("/biz/"):
            result = _get_tabs()
        for tab in result:
            assert "id" in tab
            assert "label" in tab
            assert "href" in tab
            assert "current" in tab

    def test_default_tab_is_stories(self, app: Flask):
        """No `?current_tab=…` query arg → `stories` is current."""
        with app.test_request_context("/biz/"):
            result = _get_tabs()
        currents = [t["id"] for t in result if t["current"]]
        assert currents == ["stories"]

    def test_query_param_marks_matching_tab_current(self, app: Flask):
        with app.test_request_context("/biz/?current_tab=missions"):
            result = _get_tabs()
        currents = [t["id"] for t in result if t["current"]]
        assert currents == ["missions"]

    def test_unknown_query_param_marks_no_tab_current(self, app: Flask):
        """`?current_tab=bogus` — pin the « no match → no highlight »
        behaviour. Better than highlighting the default since the
        user explicitly asked for something else."""
        with app.test_request_context("/biz/?current_tab=totally-bogus"):
            result = _get_tabs()
        currents = [t["id"] for t in result if t["current"]]
        assert currents == []

    def test_exactly_one_tab_is_current_for_each_valid_value(self, app: Flask):
        """For every entry in TABS, querying with that id marks
        exactly one tab current. Pin so a duplicate-id regression
        in TABS is caught here as well as in test_filter_specs."""
        for tab in TABS:
            with app.test_request_context(f"/biz/?current_tab={tab['id']}"):
                result = _get_tabs()
            currents = [t["id"] for t in result if t["current"]]
            assert currents == [tab["id"]], (
                f"Tab {tab['id']!r}: expected exactly one current, got {currents}"
            )

    def test_href_uses_biz_endpoint_with_query_param(self, app: Flask):
        """The `href` builds with `url_for(".biz", current_tab=tab_id)`.
        Pin so a future routing refactor that removes the query param
        from URLs gets caught."""
        with app.test_request_context("/biz/"):
            result = _get_tabs()
        for tab in result:
            assert tab["href"]
            # The query string carries `current_tab=<tab_id>`.
            assert f"current_tab={tab['id']}" in tab["href"], (
                f"href for tab {tab['id']!r} should carry "
                f"current_tab=…, got {tab['href']!r}"
            )

    def test_label_matches_tabs_constant(self, app: Flask):
        """The dict's label is taken verbatim from `TABS`. Pin so a
        future translation layer doesn't silently change labels."""
        with app.test_request_context("/biz/"):
            result = _get_tabs()
        by_id = {t["id"]: t["label"] for t in result}
        for tab in TABS:
            assert by_id[tab["id"]] == tab["label"]


class TestContractChoices:
    """The `_CONTRACT_CHOICES` constant feeds the JobOfferForm's
    contract_type SelectField. Pin the values and labels so :
    - A WTForms validator that doesn't match the form's choices
      (`validate_choice=True` by default) would silently reject
      legitimate POSTs.
    - The user-facing French labels stay stable."""

    def test_one_choice_per_contract_type(self):
        values = {v for v, _ in _CONTRACT_CHOICES}
        assert values == {ct.value for ct in ContractType}

    def test_labels_are_capitalised(self):
        for _, label in _CONTRACT_CHOICES:
            assert label[0].isupper(), (
                f"Contract label {label!r} should start uppercase"
            )

    def test_cdi_label_is_cdi(self):
        """Pin the most-used label. A localisation change like
        « CDI » → « Permanent » would silently change the publish
        form's appearance."""
        labels_by_value = dict(_CONTRACT_CHOICES)
        assert labels_by_value["CDI"] == "CDI"
        assert labels_by_value["CDD"] == "CDD"
        assert labels_by_value["STAGE"] == "Stage"

    def test_doctoral_uses_convention_label(self):
        """Pin the French wording « Convention doctorale » since it
        matches Erick's PERMISSIONS.DOCTORAL check ; a renaming on
        either side would silently break the publish flow."""
        labels_by_value = dict(_CONTRACT_CHOICES)
        assert labels_by_value["DOCTORAL"] == "Convention doctorale"
