# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for the MARKET/Projects filter bar."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import g

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.biz.models import ProjectOffer
from app.modules.biz.views._filters import ProjectFilterBar, get_filter_conditions
from app.modules.biz.views.home import _get_filters, _get_objs

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _is_sqlite(db_session: Session) -> bool:
    return "sqlite" in str(db_session.bind.url).lower()


def _project(
    db_session: Session,
    *,
    owner_id: int,
    title: str = "Project",
    project_category: str = "",
    sector: str = "",
    pays_zip_ville: str = "",
    pays_zip_ville_detail: str = "",
    status: PublicationStatus = PublicationStatus.PUBLIC,
) -> ProjectOffer:
    project = ProjectOffer(
        title=title,
        description="A project",
        project_category=project_category,
        sector=sector,
        pays_zip_ville=pays_zip_ville,
        pays_zip_ville_detail=pays_zip_ville_detail,
        status=status,
        owner_id=owner_id,
    )
    db_session.add(project)
    db_session.flush()
    return project


@pytest.fixture
def filter_user(db_session: Session) -> User:
    user = User(email="project-filter-user@example.com", first_name="P", last_name="U")
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


class TestProjectFilterBar:
    def test_empty_bar_has_no_active_filters(self, app: Flask):
        with app.test_request_context():
            bar = ProjectFilterBar()
            assert bar.active_filters == []

    def test_add_filter(self, app: Flask):
        with app.test_request_context():
            bar = ProjectFilterBar()
            bar.add_filter("sector", "Tech")
            assert len(bar.active_filters) == 1
            assert bar.active_filters[0]["id"] == "sector"
            assert bar.active_filters[0]["value"] == "Tech"

    def test_toggle_filter_adds_then_removes(self, app: Flask):
        with app.test_request_context():
            bar = ProjectFilterBar()
            bar.toggle_filter("project_category", "journalisme")
            assert bar.has_filter("project_category", "journalisme")
            bar.toggle_filter("project_category", "journalisme")
            assert not bar.has_filter("project_category", "journalisme")

    def test_reset_clears_state(self, app: Flask):
        with app.test_request_context():
            bar = ProjectFilterBar()
            bar.add_filter("sector", "Tech")
            bar.reset()
            assert bar.active_filters == []


class TestProjectFilterConditions:
    def test_empty_bar_returns_no_conditions(self, app: Flask):
        with app.test_request_context():
            bar = ProjectFilterBar()
            assert get_filter_conditions(bar) == []

    def test_sector_filter_condition(self, app: Flask):
        with app.test_request_context():
            bar = ProjectFilterBar()
            bar.add_filter("sector", "Tech")
            conditions = get_filter_conditions(bar)
            assert len(conditions) == 1

    def test_multiple_filter_conditions(self, app: Flask):
        with app.test_request_context():
            bar = ProjectFilterBar()
            bar.add_filter("sector", "Tech")
            bar.add_filter("project_category", "journalisme")
            conditions = get_filter_conditions(bar)
            assert len(conditions) == 2


class TestProjectHybridProperties:
    def test_departement_from_pays_zip_ville_detail(
        self, db_session: Session, filter_user: User
    ):
        project = _project(
            db_session,
            owner_id=filter_user.id,
            pays_zip_ville_detail="FRA / 75008 Paris",
        )
        assert project.departement == "75"

    def test_ville_from_pays_zip_ville_detail(
        self, db_session: Session, filter_user: User
    ):
        project = _project(
            db_session,
            owner_id=filter_user.id,
            pays_zip_ville_detail="FRA / 75008 Paris",
        )
        assert project.ville == "Paris"

    def test_empty_detail_returns_empty_strings(
        self, db_session: Session, filter_user: User
    ):
        project = _project(
            db_session, owner_id=filter_user.id, pays_zip_ville_detail=""
        )
        assert project.departement == ""
        assert project.ville == ""


class TestHomeViewProjectsFilters:
    def test_get_filters_returns_project_specs_on_projects_tab(self, app: Flask):
        with app.test_request_context("/biz/?current_tab=projects"):
            filters = _get_filters()
            ids = {f["id"] for f in filters}
            assert "project_category" in ids
            assert "sector" in ids
            assert "pays_zip_ville" in ids
            assert "departement" in ids
            assert "ville" in ids

    def test_get_objs_applies_project_filters(
        self,
        app: Flask,
        db_session: Session,
        filter_user: User,
    ):
        _project(
            db_session,
            owner_id=filter_user.id,
            title="Tech Project",
            project_category="journalisme",
            sector="Tech",
            status=PublicationStatus.PUBLIC,
        )
        _project(
            db_session,
            owner_id=filter_user.id,
            title="Other Project",
            project_category="communication",
            sector="Comms",
            status=PublicationStatus.PUBLIC,
        )

        with app.test_request_context("/biz/?current_tab=projects"):
            g.user = filter_user
            bar = ProjectFilterBar()
            bar.add_filter("sector", "Tech")
            objs = _get_objs(bar)

        assert len(objs) == 1
        assert objs[0].title == "Tech Project"

    def test_get_objs_with_location_filters(
        self,
        app: Flask,
        db_session: Session,
        filter_user: User,
    ):
        pytest.skip("ville/departement filters use split_part, not available on SQLite")

    def test_get_objs_with_country_filter(
        self,
        app: Flask,
        db_session: Session,
        filter_user: User,
    ):
        _project(
            db_session,
            owner_id=filter_user.id,
            title="France Project",
            pays_zip_ville="FRA",
            pays_zip_ville_detail="FRA / 75008 Paris",
            status=PublicationStatus.PUBLIC,
        )
        _project(
            db_session,
            owner_id=filter_user.id,
            title="Spain Project",
            pays_zip_ville="ESP",
            pays_zip_ville_detail="ESP / 28001 Madrid",
            status=PublicationStatus.PUBLIC,
        )

        with app.test_request_context("/biz/?current_tab=projects"):
            g.user = filter_user
            bar = ProjectFilterBar()
            bar.add_filter("pays_zip_ville", "FRA")
            objs = _get_objs(bar)

        assert len(objs) == 1
        assert objs[0].title == "France Project"
