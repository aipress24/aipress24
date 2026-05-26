# ruff: noqa: INP001
# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared helpers / constants for the regression test batches.

Lives at the package root so each `test_bugs_*.py` file can import
without re-implementing the same table-walking helpers."""

from __future__ import annotations

import re

from playwright.sync_api import Page

# Communities (CSV section labels) used to pick test profiles.
_PRESS_MEDIA = "PRESS_MEDIA"
_PRESS_RELATIONS = "PRESS_RELATIONS"

# WIP table row id patterns — extract `<id>` from a `/wip/<kind>/<id>/`
# href so `_first_id_in_table` can return an arbitrary row to drive
# regression scenarios against without coupling to seed data.
_COMM_PAT = re.compile(r"/wip/communiques/(\d+)/?")
_SUJET_PAT = re.compile(r"/wip/sujets/(\d+)/?")


def _first_id_in_table(page: Page, list_url: str, pat: re.Pattern[str]) -> str | None:
    """Return the first id matching `pat` in any href on `list_url`, or
    None. Used to pick a target row for "open & assert" style regression
    tests against WIP CRUD pages without coupling to seed data."""
    page.goto(list_url, wait_until="domcontentloaded")
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        if not href:
            continue
        m = pat.search(href)
        if m:
            return m.group(1)
    return None
