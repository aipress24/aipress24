# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""A WIP action that changes state answers only to a POST.

The session cookie is SameSite=Lax: a browser sends it along a GET from
a link on another site, not along a cross-site POST. An action reachable
by GET could be triggered by such a link.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app.flask.routing import url_for

if TYPE_CHECKING:
    from flask.testing import FlaskClient

_SETTINGS = Path(__file__).resolve().parents[4] / "etc" / "settings.toml"

STATE_CHANGING_ENDPOINTS = [
    "ArticlesWipView:publish",
    "ArticlesWipView:unpublish",
    "ArticlesWipView:delete",
    "AvisEnqueteWipView:delete",
    "CommandesWipView:validate",
    "CommandesWipView:cancel",
    "CommandesWipView:delete",
    "CommuniquesWipView:publish",
    "CommuniquesWipView:unpublish",
    "CommuniquesWipView:delete",
    "EventsWipView:publish",
    "EventsWipView:unpublish",
    "EventsWipView:delete",
    "SujetsWipView:publish",
    "SujetsWipView:unpublish",
    "SujetsWipView:accept",
    "SujetsWipView:refuse",
    "SujetsWipView:delete",
]


@pytest.mark.parametrize("endpoint", STATE_CHANGING_ENDPOINTS)
def test_a_get_is_refused(logged_in_client: FlaskClient, endpoint: str) -> None:
    response = logged_in_client.get(url_for(endpoint, id=1))

    assert response.status_code == 405


@pytest.mark.parametrize("cookie", ["SESSION_COOKIE", "REMEMBER_COOKIE"])
def test_no_cookie_goes_along_a_cross_site_post(cookie: str) -> None:
    """The session and the « remember me » cookie both stay home on a
    cross-site POST: either one alone would authenticate it. The test app
    runs on `TestConfig`, so the check reads the settings file."""
    settings = tomllib.loads(_SETTINGS.read_text())
    key = f"{cookie}_SAMESITE"

    assert settings["default"][key] == "Lax"
    for env in ("development", "production"):
        assert settings[env].get(key, "Lax") == "Lax"
