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
from app.modules.kyc.ontology_loader import get_ontology_content
from app.services.taxonomies._models import TaxonomyEntry

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
            bar.add_filter("pays_zip_ville", "FRA")
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
    def test_get_filters_returns_first_line_specs_on_jobs_tab(self, app: Flask):
        with app.test_request_context("/biz/?current_tab=jobs"):
            filters = _get_filters()
            ids = [f["id"] for f in filters]
            assert ids[:5] == [
                "statut",
                "domain",
                "pays_zip_ville",
                "departement",
                "ville",
            ]

    def test_active_filter_tag_strips_taxonomy_prefix(self, app: Flask):
        with app.test_request_context("/biz/?current_tab=jobs"):
            bar = JobFilterBar()
            bar.add_filter(
                "type_emploi_pro_studient", "JOB BOARD / STUDIENT / Offre de stage"
            )
            active = bar.active_filters
            assert len(active) == 1
            assert active[0]["label"] == "Offre de stage"

    def test_get_filters_show_student_filters_when_student_active(self, app: Flask):
        with app.test_request_context("/biz/?current_tab=jobs"):
            bar = JobFilterBar()
            bar.add_filter("statut", "STATUT / Etudiant.e")
            filters = _get_filters(job_filter_bar=bar)
            ids = [f["id"] for f in filters]
            assert ids[:5] == [
                "statut",
                "domain",
                "pays_zip_ville",
                "departement",
                "ville",
            ]
            extra_ids = set(ids[5:])
            assert "type_emploi_pro_studient" in extra_ids
            assert "niveau_etude" in extra_ids
            assert "matiere_etudiee" in extra_ids
            assert "langues" in extra_ids
            assert "sector" in extra_ids

    def test_get_filters_show_pro_domain_specific_filters(self, app: Flask):
        with app.test_request_context("/biz/?current_tab=jobs"):
            bar = JobFilterBar()
            bar.add_filter("statut", "STATUT / Professionnel.le")
            bar.add_filter("domain", "Journalisme")
            filters = _get_filters(job_filter_bar=bar)
            ids = [f["id"] for f in filters]
            assert ids[:5] == [
                "statut",
                "domain",
                "pays_zip_ville",
                "departement",
                "ville",
            ]
            extra_ids = set(ids[5:])
            assert "type_emploi_pro_journaliste" in extra_ids
            assert "competence_journalisme" in extra_ids
            assert "niveau_etude" in extra_ids
            assert "langues" in extra_ids
            assert "sector" in extra_ids

    def test_get_filters_show_pro_communication_innovation_filters(self, app: Flask):
        with app.test_request_context("/biz/?current_tab=jobs"):
            bar_com = JobFilterBar()
            bar_com.add_filter("statut", "STATUT / Professionnel.le")
            bar_com.add_filter("domain", "Communication")
            filters_com = _get_filters(job_filter_bar=bar_com)
            extra_ids_com = {f["id"] for f in filters_com[5:]}
            assert "type_emploi_pro_communicant" in extra_ids_com
            assert "competence_relation_presse" in extra_ids_com

            bar_inn = JobFilterBar()
            bar_inn.add_filter("statut", "STATUT / Professionnel.le")
            bar_inn.add_filter("domain", "Innovation")
            filters_inn = _get_filters(job_filter_bar=bar_inn)
            extra_ids_inn = {f["id"] for f in filters_inn[5:]}
            assert "type_emploi_pro_innovation" in extra_ids_inn
            assert "competence_innovation" in extra_ids_inn

    def test_pro_domain_ontology_load_correctly(self, app: Flask, db_session: Session):
        db_session.add(
            TaxonomyEntry(
                taxonomy_name="innovation_skills",
                category="",
                seq=0,
                name="INNOVATION_SKILLS / IA Générative",
                value="INNOVATION_SKILLS / IA Générative",
            )
        )
        db_session.add(
            TaxonomyEntry(
                taxonomy_name="press_relations_skills",
                category="",
                seq=0,
                name="PRESS_RELATIONS_SKILLS / Communiqué",
                value="PRESS_RELATIONS_SKILLS / Communiqué",
            )
        )
        db_session.flush()

        get_ontology_content.cache.clear()

        with app.test_request_context("/biz/?current_tab=jobs"):
            bar = JobFilterBar()
            spec_inn = {
                "id": "competence_innovation",
                "ontology_key": "competence_innovation",
                "label_function": lambda x: x,
            }
            opts_inn = bar._options_for_spec(spec_inn)
            assert len(opts_inn) == 1
            assert opts_inn[0]["id"] == "INNOVATION_SKILLS / IA Générative"

            spec_com = {
                "id": "competence_relation_presse",
                "ontology_key": "competence_relation_presse",
                "label_function": lambda x: x,
            }
            opts_com = bar._options_for_spec(spec_com)
            assert len(opts_com) == 1
            assert opts_com[0]["id"] == "PRESS_RELATIONS_SKILLS / Communiqué"

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
