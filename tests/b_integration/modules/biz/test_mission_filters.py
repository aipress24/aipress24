# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for the MARKET/Missions filter bar and deadline sort."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from flask import g

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.biz.models import MissionCategory, MissionOffer
from app.modules.biz.views._filters import (
    MissionFilterBar,
    get_mission_filter_conditions,
)
from app.modules.biz.views.home import _get_filters, _get_objs

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _mission(
    db_session: Session,
    *,
    owner_id: int,
    title: str = "Mission",
    category: MissionCategory | None = MissionCategory.JOURNALISME,
    sector: str = "",
    pays_zip_ville: str = "",
    pays_zip_ville_detail: str = "",
    deadline: datetime | None = None,
    status: PublicationStatus = PublicationStatus.PUBLIC,
) -> MissionOffer:
    mission = MissionOffer(
        title=title,
        description="A mission offer",
        category=category,
        sector=sector,
        pays_zip_ville=pays_zip_ville,
        pays_zip_ville_detail=pays_zip_ville_detail,
        deadline=deadline,
        status=status,
        owner_id=owner_id,
    )
    db_session.add(mission)
    db_session.flush()
    return mission


@pytest.fixture
def filter_user(db_session: Session) -> User:
    user = User(email="mission-filter-user@example.com", first_name="M", last_name="U")
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


class TestMissionFilterBar:
    def test_empty_bar_has_no_active_filters(self, app: Flask):
        with app.test_request_context():
            bar = MissionFilterBar()
            assert bar.active_filters == []

    def test_add_filter(self, app: Flask):
        with app.test_request_context():
            bar = MissionFilterBar()
            bar.add_filter("type_mission", "journalisme")
            assert len(bar.active_filters) == 1
            assert bar.active_filters[0]["id"] == "type_mission"
            assert bar.active_filters[0]["value"] == "journalisme"

    def test_toggle_filter_adds_then_removes(self, app: Flask):
        with app.test_request_context():
            bar = MissionFilterBar()
            bar.toggle_filter("type_mission", "journalisme")
            assert bar.has_filter("type_mission", "journalisme")
            bar.toggle_filter("type_mission", "journalisme")
            assert not bar.has_filter("type_mission", "journalisme")

    def test_reset_clears_state(self, app: Flask):
        with app.test_request_context():
            bar = MissionFilterBar()
            bar.add_filter("sector", "Tech")
            bar.reset()
            assert bar.active_filters == []


class TestMissionFilterConditions:
    def test_empty_bar_returns_no_conditions(self, app: Flask):
        with app.test_request_context():
            bar = MissionFilterBar()
            assert get_mission_filter_conditions(bar) == []

    def test_type_mission_filter_condition(self, app: Flask):
        with app.test_request_context():
            bar = MissionFilterBar()
            bar.add_filter("type_mission", "journalisme")
            conditions = get_mission_filter_conditions(bar)
            assert len(conditions) == 1

    def test_multiple_filter_conditions(self, app: Flask):
        with app.test_request_context():
            bar = MissionFilterBar()
            bar.add_filter("sector", "Tech")
            bar.add_filter("type_mission", "journalisme")
            conditions = get_mission_filter_conditions(bar)
            assert len(conditions) == 2


class TestMissionHybridProperties:
    def test_departement_from_pays_zip_ville_detail(
        self, db_session: Session, filter_user: User
    ):
        m = _mission(
            db_session,
            owner_id=filter_user.id,
            pays_zip_ville_detail="FRA / 75008 Paris",
        )
        assert m.departement == "75"

    def test_ville_from_pays_zip_ville_detail(
        self, db_session: Session, filter_user: User
    ):
        m = _mission(
            db_session,
            owner_id=filter_user.id,
            pays_zip_ville_detail="FRA / 75008 Paris",
        )
        assert m.ville == "Paris"

    def test_type_mission_property(self, db_session: Session, filter_user: User):
        m = _mission(
            db_session,
            owner_id=filter_user.id,
            category=MissionCategory.JOURNALISME,
        )
        assert m.type_mission == "journalisme"

    def test_empty_detail_returns_empty_strings(
        self, db_session: Session, filter_user: User
    ):
        m = _mission(db_session, owner_id=filter_user.id, pays_zip_ville_detail="")
        assert m.departement == ""
        assert m.ville == ""


class TestHomeViewMissionsFilters:
    def test_get_filters_returns_mission_specs_on_missions_tab(self, app: Flask):
        with app.test_request_context("/biz/?current_tab=missions"):
            filters = _get_filters()
            ids = {f["id"] for f in filters}
            assert "type_mission" in ids
            assert "sector" in ids
            assert "pays_zip_ville" in ids
            assert "departement" in ids
            assert "ville" in ids

    def test_get_objs_applies_mission_filters(
        self, app: Flask, db_session: Session, filter_user: User
    ):
        m1 = _mission(
            db_session,
            owner_id=filter_user.id,
            title="Tech Communication",
            category=MissionCategory.COMMUNICATION,
            sector="Tech",
        )
        m2 = _mission(
            db_session,
            owner_id=filter_user.id,
            title="Health Communication",
            category=MissionCategory.COMMUNICATION,
            sector="Health",
        )

        with app.test_request_context("/biz/?current_tab=missions"):
            g.user = filter_user
            bar = MissionFilterBar()
            bar.add_filter("sector", "Tech")
            objs = _get_objs(mission_filter_bar=bar)
            obj_ids = [o.id for o in objs]
            assert m1.id in obj_ids
            assert m2.id not in obj_ids

    def test_get_objs_missions_ordered_by_deadline(
        self, app: Flask, db_session: Session, filter_user: User
    ):
        now = datetime.now(UTC)
        m_later = _mission(
            db_session,
            owner_id=filter_user.id,
            title="Later Deadline",
            category=MissionCategory.COMMUNICATION,
            deadline=now + timedelta(days=10),
        )
        m_earlier = _mission(
            db_session,
            owner_id=filter_user.id,
            title="Earlier Deadline",
            category=MissionCategory.COMMUNICATION,
            deadline=now + timedelta(days=2),
        )

        with app.test_request_context("/biz/?current_tab=missions"):
            g.user = filter_user
            objs = _get_objs()
            mission_ids = [o.id for o in objs if o.id in (m_later.id, m_earlier.id)]
            assert mission_ids == [m_earlier.id, m_later.id]
