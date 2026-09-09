# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The sign-up wizard renders on a session that holds nothing yet.

Regression: the #0333 fix read `form_raw_results` from the session to
learn which values a profile already held. `SessionService.get` raises
`KeyError` without an explicit default, so on a fresh session — every
first-time sign-up — `/kyc/wizard/<profile>` answered 500. No test
covered the anonymous first visit, and the browser test written
alongside the fix asserted the absence of an error message, which a
500 page also lacks.
"""

from __future__ import annotations

import pytest

PROFILES = ["P002", "P010", "P015"]


@pytest.fixture
def csrf_client(app):
    """The suite disables CSRF, but `wizard.html` renders
    `form.csrf_token`, which does not exist when it is off — so the
    page could not be rendered under the default test config at all.
    That is why the 500 reached production unnoticed."""
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        yield app.test_client()
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


@pytest.mark.parametrize("profile_id", PROFILES)
def test_the_wizard_renders_for_a_first_time_visitor(csrf_client, profile_id):
    response = csrf_client.get(f"/kyc/wizard/{profile_id}")

    assert response.status_code == 200
    assert b"<form" in response.data


def test_the_wizard_renders_its_fields(csrf_client):
    """A 200 alone would pass on an error page rendered with a 200."""
    body = csrf_client.get("/kyc/wizard/P002").data.decode()

    assert 'name="civilite"' in body
