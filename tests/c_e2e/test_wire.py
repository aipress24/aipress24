# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask.testing import FlaskClient


def test_wire(logged_in_client: FlaskClient) -> None:
    """Tests the main wire page."""
    response = logged_in_client.get("/wire/tab/wall")
    assert response.status_code == 200
