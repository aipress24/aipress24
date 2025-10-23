# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient


def test_home(app: Flask, logged_in_client: FlaskClient) -> None:
    """Tests that the homepage is accessible after login."""
    response = logged_in_client.get("/")
    assert response.status_code in {200, 302, 308}


def test_backdoor(app: Flask, logged_in_client: FlaskClient) -> None:
    """Tests that the backdoor login utility works and is accessible."""
    response = logged_in_client.get("/backdoor/")
    assert response.status_code in {200, 302}


def test_wip(app: Flask, logged_in_client: FlaskClient) -> None:
    """Tests that the main WIP page is accessible."""
    response = logged_in_client.get("/wip")
    assert response.status_code in {200, 302, 308}

    response = logged_in_client.get("/wip/contents?mode=list")
    assert response.status_code in {200, 302}
