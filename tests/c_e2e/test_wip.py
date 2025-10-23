# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask.testing import FlaskClient


def test_wip(logged_in_client: FlaskClient) -> None:
    """Tests that the /wip route successfully redirects."""
    response = logged_in_client.get("/wip")
    assert response.status_code in {200, 302, 308}


def test_contents(logged_in_client: FlaskClient) -> None:
    """Tests the content creation page."""
    response = logged_in_client.get("/wip/contents?mode=list")
    assert response.status_code in {200, 302}

    response = logged_in_client.get("/wip/contents?mode=create&doc_type=article")
    assert response.status_code in {200, 302}


def test_sujets(logged_in_client: FlaskClient) -> None:
    """Tests the 'sujets' page."""
    response = logged_in_client.get("/wip/sujets")
    assert response.status_code in {200, 302}
