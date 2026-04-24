# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for the admin mini-CMS surface.

GET-only path tests. End-to-end POST flows (edit, preview, public
route) live under `tests/c_e2e/` because they commit and thus need
the fresh_db isolation pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from svcs.flask import container

from app.modules.admin.cms import CorporatePageService

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def cgv_page(db_session: Session):
    svc = container.get(CorporatePageService)
    svc.upsert(
        slug="CGV-BusinessWall",
        title="CGV BusinessWall",
        body_md="# Conditions\n\nContenu initial.",
    )
    db_session.flush()


@pytest.mark.usefixtures("cgv_page")
def test_list_page_renders(admin_client: FlaskClient) -> None:
    resp = admin_client.get("/admin/cms")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "CGV-BusinessWall" in body
    assert "CGV BusinessWall" in body


@pytest.mark.usefixtures("cgv_page")
def test_edit_get_shows_textarea(admin_client: FlaskClient) -> None:
    resp = admin_client.get("/admin/cms/CGV-BusinessWall/edit")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Contenu initial" in body
    assert 'name="body_md"' in body
    assert 'name="title"' in body
