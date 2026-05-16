# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for the admin mini-CMS surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from svcs.flask import container

from app.modules.admin.cms import CorporatePageService

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from app.models.auth import User


@pytest.fixture
def cgv_page(db_session):
    svc = container.get(CorporatePageService)
    svc.upsert(
        slug="CGV-BusinessWall",
        title="CGV BusinessWall",
        body_md="# Conditions\n\nContenu initial.",
    )
    db_session.commit()


@pytest.mark.usefixtures("admin_user", "cgv_page")
class TestCorporatePagesEdit:
    def test_edit_post_updates_page(
        self,
        admin_client: FlaskClient,
    ):
        resp = admin_client.post(
            "/admin/cms/CGV-BusinessWall/edit",
            data={"title": "Nouveau titre", "body_md": "Nouveau contenu."},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

        svc = container.get(CorporatePageService)
        updated = svc.get(slug="CGV-BusinessWall")
        assert updated is not None
        assert updated.title == "Nouveau titre"
        assert updated.body_md == "Nouveau contenu."

    def test_edit_post_records_updated_by(
        self,
        admin_client: FlaskClient,
        admin_user: User,
    ):
        admin_client.post(
            "/admin/cms/CGV-BusinessWall/edit",
            data={"title": "t", "body_md": "b"},
            follow_redirects=False,
        )
        svc = container.get(CorporatePageService)
        page = svc.get(slug="CGV-BusinessWall")
        assert page is not None
        assert page.updated_by_id == admin_user.id

    def test_edit_unknown_slug_redirects(
        self,
        admin_client: FlaskClient,
    ):
        resp = admin_client.get("/admin/cms/does-not-exist/edit")
        assert resp.status_code in (302, 303)


@pytest.mark.usefixtures("admin_user")
class TestCorporatePagesPreview:
    def test_preview_renders_markdown(
        self,
        admin_client: FlaskClient,
    ):
        resp = admin_client.post(
            "/admin/cms/preview",
            data={"body_md": "# Title\n\n**bold**"},
        )
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "<h1>" in body
        assert "Title" in body
        assert "<strong>" in body

    def test_preview_strips_script_tags_and_content(
        self,
        admin_client: FlaskClient,
    ):
        resp = admin_client.post(
            "/admin/cms/preview",
            data={"body_md": '<script>alert("xss")</script>hello'},
        )
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "<script>" not in body
        assert "alert" not in body
        assert "hello" in body

    def test_preview_strips_iframe(
        self,
        admin_client: FlaskClient,
    ):
        resp = admin_client.post(
            "/admin/cms/preview",
            data={"body_md": '<iframe src="http://evil"></iframe>visible'},
        )
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "<iframe" not in body
        assert "evil" not in body
        assert "visible" in body


class TestPublicPageRoute:
    def test_serves_db_row_when_present(
        self,
        client: FlaskClient,
        db_session,
    ):
        svc = container.get(CorporatePageService)
        svc.upsert(
            slug="CGV-BusinessWall",
            title="CGV depuis la base",
            body_md="# Du contenu en base\n\nCeci vient de la DB.",
        )
        db_session.commit()

        resp = client.get("/page/CGV-BusinessWall")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "Du contenu en base" in body
        assert "Ceci vient de la DB." in body

    def test_served_db_page_is_sanitized_like_preview(
        self,
        client: FlaskClient,
        db_session,
    ):
        """Regression (audit 2026-05-15, S2): the public served path
        must sanitize stored HTML the same way the admin preview does.

        `cms_preview` strips `<script>`/`<iframe>` + `bleach.clean`s,
        but `public/views/page.py:_render_md_content` did a bare
        `markdown(body_md)` into `{{ content|safe }}`. An admin who
        pasted hostile HTML saw a *clean* preview, published, and the
        public page (anonymous audience) then served the live payload.
        Both paths must go through one shared sanitized renderer.
        """
        svc = container.get(CorporatePageService)
        svc.upsert(
            slug="CGV-BusinessWall",
            title="Hostile",
            body_md=(
                '<script>alert("xss")</script>\n\n'
                '<img src=x onerror="alert(1)">\n\n'
                '<iframe src="http://evil"></iframe>\n\nvisible text'
            ),
        )
        db_session.commit()

        resp = client.get("/page/CGV-BusinessWall")
        assert resp.status_code == 200
        body = resp.data.decode()

        # Payload-specific signatures must be gone (the page layout
        # legitimately contains its own <script> chrome, so assert on
        # the injected vectors, not a bare "<script>").
        assert 'alert("xss")' not in body
        assert "<script>alert" not in body
        assert "onerror=" not in body
        assert "<iframe" not in body
        assert "http://evil" not in body
        # Benign content still rendered.
        assert "visible text" in body

    def test_falls_back_to_filesystem_when_no_db_row(
        self,
        client: FlaskClient,
    ):
        # No DB row seeded — the filesystem file should be served.
        resp = client.get("/page/CGV-BusinessWall")
        assert resp.status_code == 200
        body = resp.data.decode()
        # Content from static-pages/CGV-BusinessWall.md.
        assert "Conditions Générales" in body

    def test_returns_404_on_unknown_slug(
        self,
        client: FlaskClient,
    ):
        resp = client.get("/page/definitely-not-a-real-slug")
        assert resp.status_code == 404
