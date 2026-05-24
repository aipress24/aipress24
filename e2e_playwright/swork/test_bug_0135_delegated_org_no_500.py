# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0135 (Erick, 2026-05-14) regression.

Igor Fransèches (PR agency) publishes events « pour » his client
Fake-Davi Logistique. When Erick clicks through SOCIAL → Organisations
→ Fake-Davi Logistique, the server returns a 500.

We cannot pin the exact organisation id from outside the test DB, so the
test walks all visible organisation cards on `/swork/organisations`,
opens each detail page (which is what Erick did), and asserts that NONE
of them return a 500. A single 500 across the whole listing is enough
to surface the regression. The 500 reported on 2026-05-14 was specific
to the delegated-events org, so failure here matches Erick's report.

Read-only ; no DB mutation.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect


# Detail pages live at /swork/organisations/<slug-or-id> ; we match
# href endings so we don't depend on the exact id format.
_ORG_HREF_RE = re.compile(r"^/swork/organisations/[^/?#]+$")


def test_no_500_when_opening_each_organisation_detail_page(
    page: Page, base_url: str, profile, login
) -> None:
    """No org-detail page in the directory should 500 (#0135).

    Walks every org link surfaced by the listing and opens each detail
    page. A single 500 fails the test. Read-only.
    """
    login(profile("PRESS_MEDIA"))

    list_url = f"{base_url}/swork/organisations"
    response = page.goto(list_url, wait_until="domcontentloaded")
    assert response is not None
    assert response.status == 200, (
        f"organisations listing itself returned {response.status}"
    )

    # Collect distinct org-detail hrefs from the listing.
    hrefs = page.evaluate(
        """() => Array.from(new Set(
            Array.from(document.querySelectorAll('a[href]'))
              .map(a => new URL(a.href, location.href).pathname)
              .filter(h => /^\\/swork\\/organisations\\/[^\\/?#]+$/.test(h))
        ))"""
    )
    if not hrefs:
        pytest.skip("no organisation links found on /swork/organisations")

    failures: list[tuple[str, int]] = []
    for href in hrefs:
        url = f"{base_url}{href}"
        # Use a fresh navigation so a per-page 500 doesn't poison the
        # next iteration's cookies / context.
        resp = page.goto(url, wait_until="domcontentloaded")
        if resp is None:
            failures.append((href, -1))
            continue
        if resp.status >= 500:
            failures.append((href, resp.status))

    assert not failures, (
        f"#0135 regression: {len(failures)} organisation detail page(s) "
        f"returned 5xx — first: {failures[:5]}"
    )

    # And the listing should not show « Internal Server Error » text
    # leaked into a card embed (rare but worth guarding).
    expect(page.locator("body")).not_to_contain_text("Internal Server Error")
