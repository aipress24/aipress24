# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
E2E tests.

These tests use Flask's test client with a logged-in user session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from werkzeug.routing import Rule


def test_home(logged_in_client: FlaskClient) -> None:
    """Tests the homepage again for good measure."""
    response = logged_in_client.get("/")
    assert response.status_code in {200, 302, 308}


def test_backdoor(logged_in_client: FlaskClient) -> None:
    """Tests backdoor access routes."""
    response = logged_in_client.get("/backdoor/")
    assert response.status_code in {200, 302}


def test_most_routes(app: Flask, logged_in_client: FlaskClient) -> None:
    """Iterates through most of the app's routes to check for crashes."""
    ignore_prefixes = [
        "/_",
        "/static/",
        # Temp
        "/search",
        "/wallet/create-checkout-session",
        # FIXME: Missing params ?
        "/wip/billing/get_pdf",
        "/wip/billing/get_csv",
        # FIXME: AttributeError: type object 'BaseContent' has no attribute 'status'
        "/wip/comroom/json_data",
        "/wip/newsroom/json_data",
        # FIXME: 'items' is undefined
        "/wip/alt-content",
    ]

    rules: list[Rule] = list(app.url_map.iter_rules())
    for rule in rules:
        if any(rule.rule.startswith(p) for p in ignore_prefixes):
            continue

        if "<" in rule.rule:
            continue

        print(f"Visiting route: {rule.rule}")
        response = logged_in_client.get(rule.rule)
        # Allow for successful responses or redirects
        assert response.status_code in {
            200,
            302,
            308,
        }, f"Request failed on {rule.rule} with status {response.status_code}"


def test_marketing(logged_in_client: FlaskClient) -> None:
    """Tests static marketing pages."""
    pages = [
        "/page/a-propos",
        "/page/pricing",
    ]
    for page in pages:
        response = logged_in_client.get(page)
        assert response.status_code in {200, 302, 308}, f"Request failed on {page}"
