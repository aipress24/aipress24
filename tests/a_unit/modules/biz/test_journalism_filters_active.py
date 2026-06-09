# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `_journalism_filters_active` in
`app.modules.biz.views.home`.

This helper is the gate that decides whether the expanded journalism
filter sidebar appears alongside the generic filters (ticket #0202).
The contract is :

    return current_tab == "missions" AND category == "journalisme"

Both flags come from `request.args` query parameters. We test it
inside `app.test_request_context(...)` — no DB, no full request
dispatch — so it lands cleanly in a_unit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.biz.views.home import _journalism_filters_active

if TYPE_CHECKING:
    from flask import Flask


class TestJournalismFiltersActive:
    def test_active_on_missions_with_journalism(self, app: Flask):
        with app.test_request_context(
            "/biz/?current_tab=missions&category=journalisme"
        ):
            assert _journalism_filters_active() is True

    def test_inactive_on_missions_without_category(self, app: Flask):
        """Missions tab with no category filter : the generic filter
        sidebar applies, not the journalism one."""
        with app.test_request_context("/biz/?current_tab=missions"):
            assert _journalism_filters_active() is False

    def test_inactive_on_missions_with_other_category(self, app: Flask):
        with app.test_request_context(
            "/biz/?current_tab=missions&category=communication"
        ):
            assert _journalism_filters_active() is False

    def test_inactive_on_projects_with_journalism(self, app: Flask):
        """Even when category=journalisme, the projects tab uses its
        own filter set (not Erick's #0202 journalism filters which
        target missions). Pin the asymmetry."""
        with app.test_request_context(
            "/biz/?current_tab=projects&category=journalisme"
        ):
            assert _journalism_filters_active() is False

    def test_inactive_on_default_tab(self, app: Flask):
        """No `current_tab` query param → defaults to `stories` →
        journalism filters never apply."""
        with app.test_request_context("/biz/?category=journalisme"):
            assert _journalism_filters_active() is False

    def test_inactive_on_jobs_tab(self, app: Flask):
        with app.test_request_context("/biz/?current_tab=jobs&category=journalisme"):
            assert _journalism_filters_active() is False

    def test_case_sensitivity(self, app: Flask):
        """`current_tab` / `category` comparison is case-sensitive. A
        misspelling like `?category=Journalisme` should NOT activate
        the filter — pin so a future « case-insensitive » regression
        is caught and made explicit."""
        with app.test_request_context(
            "/biz/?current_tab=missions&category=Journalisme"
        ):
            assert _journalism_filters_active() is False

    def test_empty_category_string(self, app: Flask):
        """`?category=` (empty value) is NOT journalism."""
        with app.test_request_context("/biz/?current_tab=missions&category="):
            assert _journalism_filters_active() is False
