# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask.testing import FlaskClient


def test_wip(logged_in_client: FlaskClient) -> None:
    """Tests that the /wip route successfully redirects."""
    # The actual WIP route is /wip/wip
    response = logged_in_client.get("/wip/dashboard")
    assert response.status_code == 200


def test_contents(logged_in_client: FlaskClient) -> None:
    """Tests the content pages."""
    # Test articles list (there's no generic /wip/contents route)
    response = logged_in_client.get("/wip/articles/")
    assert response.status_code == 200

    # Test creating new article
    response = logged_in_client.get("/wip/articles/new/")
    assert response.status_code == 200


def test_sujets(logged_in_client: FlaskClient) -> None:
    """Tests the 'sujets' page."""
    response = logged_in_client.get("/wip/sujets/")
    assert response.status_code == 200
