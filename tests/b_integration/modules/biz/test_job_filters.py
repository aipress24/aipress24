# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for the MARKET/Job Board filter bar."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import g

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.biz.models import ContractType, JobOffer
from app.modules.biz.views._filters import JobFilterBar, get_job_filter_conditions
from app.modules.biz.views.home import _get_filters, _get_objs

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _job(
    db_session: Session,
    *,
    owner_id: int,
    title: str = "Job",
    contract_type: ContractType = ContractType.CDI,
    sector: str = "",
    pays_zip_ville: str = "",
    pays_zip_ville_detail: str = "",
    status: PublicationStatus = PublicationStatus.PUBLIC,
) -> JobOffer:
    job = JobOffer(
        title=title,
        description="A job offer",
        contract_type=contract_type,
        sector=sector,
        pays_zip_ville=pays_zip_ville,
        pays_zip_ville_detail=pays_zip_ville_detail,
        status=status,
        owner_id=owner_id,
    )
    db_session.add(job)
    db_session.flush()
    return job


@pytest.fixture
def filter_user(db_session: Session) -> User:
    user = User(email="job-filter-user@example.com", first_name="J", last_name="U")
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


class TestJobFilterBar:
    def test_empty_bar_has_no_active_filters(self, app: Flask):
        with app.test_request_context():
            bar = JobFilterBar()
            assert bar.active_filters == []

    def test_add_filter(self, app: Flask):
        with app.test_request_context():
            bar = JobFilterBar()
            bar.add_filter("sector", "Tech")
            assert len(bar.active_filters) == 1
            assert bar.active_filters[0]["id"] == "sector"
            assert bar.active_filters[0]["value"] == "Tech"

    def test_toggle_filter_adds_then_removes(self, app: Flask):
        with app.test_request_context():
            bar = JobFilterBar()
            bar.toggle_filter("contract_type", "CDI")
            assert bar.has_filter("contract_type", "CDI")
            bar.toggle_filter("contract_type", "CDI")
            assert not bar.has_filter("contract_type", "CDI")

    def test_reset_clears_state(self, app: Flask):
        with app.test_request_context():
            bar = JobFilterBar()
            bar.add_filter("sector", "Tech")
            bar.reset()
            assert bar.active_filters == []


class TestJobFilterConditions:
    def test_empty_bar_returns_no_conditions(self, app: Flask):
        with app.test_request_context():
            bar = JobFilterBar()
            assert get_job_filter_conditions(bar) == []

    def test_sector_filter_condition(self, app: Flask):
        with app.test_request_context():
            bar = JobFilterBar()
            bar.add_filter("sector", "Tech")
            conditions = get_job_filter_conditions(bar)
            assert len(conditions) == 1

    def test_multiple_filter_conditions(self, app: Flask):
        with app.test_request_context():
            bar = JobFilterBar()
            bar.add_filter("sector", "Tech")
            bar.add_filter("contract_type", "CDI")
            conditions = get_job_filter_conditions(bar)
            assert len(conditions) == 2


class TestJobHybridProperties:
    def test_departement_from_pays_zip_ville_detail(
        self, db_session: Session, filter_user: User
    ):
        job = _job(
            db_session,
            owner_id=filter_user.id,
            pays_zip_ville_detail="FRA / 75008 Paris",
        )
        assert job.departement == "75"

    def test_ville_from_pays_zip_ville_detail(
        self, db_session: Session, filter_user: User
    ):
        job = _job(
            db_session,
            owner_id=filter_user.id,
            pays_zip_ville_detail="FRA / 75008 Paris",
        )
        assert job.ville == "Paris"

    def test_empty_detail_returns_empty_strings(
        self, db_session: Session, filter_user: User
    ):
        job = _job(db_session, owner_id=filter_user.id, pays_zip_ville_detail="")
        assert job.departement == ""
        assert job.ville == ""


class TestHomeViewJobsFilters:
    def test_get_filters_returns_job_specs_on_jobs_tab(self, app: Flask):
        with app.test_request_context("/biz/?current_tab=jobs"):
            filters = _get_filters()
            ids = {f["id"] for f in filters}
            assert "sector" in ids
            assert "contract_type" in ids
            assert "pays_zip_ville" in ids
            assert "departement" in ids
            assert "ville" in ids

    def test_get_objs_applies_job_filters(
        self,
        app: Flask,
        db_session: Session,
        filter_user: User,
    ):
        _job(
            db_session,
            owner_id=filter_user.id,
            title="Tech Job",
            contract_type=ContractType.CDI,
            sector="Tech",
            status=PublicationStatus.PUBLIC,
        )
        _job(
            db_session,
            owner_id=filter_user.id,
            title="Other Job",
            contract_type=ContractType.CDD,
            sector="Comms",
            status=PublicationStatus.PUBLIC,
        )

        with app.test_request_context("/biz/?current_tab=jobs"):
            g.user = filter_user
            bar = JobFilterBar()
            bar.add_filter("sector", "Tech")
            objs = _get_objs(job_filter_bar=bar)

        assert len(objs) == 1
        assert objs[0].title == "Tech Job"

    def test_get_objs_with_country_filter(
        self,
        app: Flask,
        db_session: Session,
        filter_user: User,
    ):
        _job(
            db_session,
            owner_id=filter_user.id,
            title="France Job",
            pays_zip_ville="FRA",
            pays_zip_ville_detail="FRA / 75008 Paris",
            status=PublicationStatus.PUBLIC,
        )
        _job(
            db_session,
            owner_id=filter_user.id,
            title="Spain Job",
            pays_zip_ville="ESP",
            pays_zip_ville_detail="ESP / 28001 Madrid",
            status=PublicationStatus.PUBLIC,
        )

        with app.test_request_context("/biz/?current_tab=jobs"):
            g.user = filter_user
            bar = JobFilterBar()
            bar.add_filter("pays_zip_ville", "FRA")
            objs = _get_objs(job_filter_bar=bar)

        assert len(objs) == 1
        assert objs[0].title == "France Job"
