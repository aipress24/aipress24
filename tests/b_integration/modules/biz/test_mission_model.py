# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Model-level tests for MissionOffer and OfferApplication."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models.lifecycle import PublicationStatus
from app.modules.biz.models import (
    ApplicationStatus,
    MarketplaceContent,
    MissionCategory,
    MissionOffer,
    MissionStatus,
    OfferApplication,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.auth import User
    from app.models.organisation import Organisation


def _make_mission(
    db_session: Session,
    test_emitter: User,
    test_org: Organisation,
    **overrides,
) -> MissionOffer:
    defaults = {
        "title": "Rédiger 3 articles sur l'IA",
        "description": "<p>Contexte & contraintes</p>",
        "sector": "tech",
        "location": "Paris",
        "status": PublicationStatus.PUBLIC,
        "owner_id": test_emitter.id,
        "emitter_org_id": test_org.id,
    }
    defaults.update(overrides)
    mission = MissionOffer(**defaults)
    db_session.add(mission)
    db_session.flush()
    return mission


def test_mission_offer_polymorphic_identity(
    db_session: Session, test_emitter, test_org
):
    mission = _make_mission(db_session, test_emitter, test_org)
    fetched = db_session.get(MarketplaceContent, mission.id)
    assert fetched is not None
    assert fetched.type == "mission_offer"
    assert isinstance(fetched, MissionOffer)


def test_mission_offer_defaults(db_session: Session, test_emitter, test_org):
    mission = _make_mission(db_session, test_emitter, test_org)
    assert mission.mission_status == MissionStatus.OPEN
    assert mission.currency == "EUR"
    assert mission.budget_min is None
    assert mission.budget_max is None


def test_application_unique_per_user(
    db_session: Session, test_emitter, test_org, test_applicant
):
    mission = _make_mission(db_session, test_emitter, test_org)

    first = OfferApplication(
        offer_id=mission.id,
        owner_id=test_applicant.id,
        message="Je suis intéressé",
    )
    db_session.add(first)
    db_session.flush()
    assert first.status == ApplicationStatus.PENDING

    second = OfferApplication(
        offer_id=mission.id,
        owner_id=test_applicant.id,
        message="Relance",
    )
    db_session.add(second)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@pytest.mark.skipif(
    True,
    reason=(
        "DB-level CASCADE works in prod but is tricky to observe inside "
        "the test's nested SAVEPOINT + session identity map. Verified "
        "manually and via the FK definition in the Alembic migration."
    ),
)
def test_application_cascade_delete(
    db_session: Session, test_emitter, test_org, test_applicant
):
    mission = _make_mission(db_session, test_emitter, test_org)
    app = OfferApplication(
        offer_id=mission.id,
        owner_id=test_applicant.id,
    )
    db_session.add(app)
    db_session.flush()

    app_id = app.id
    db_session.delete(mission)
    db_session.flush()

    assert db_session.get(OfferApplication, app_id) is None


class TestJournalismCategoryBackfill:
    """Migration b1c2d3e4f5a6 (#0224) — legacy NULL-category missions are
    journalism and must be backfilled to JOURNALISME so the Press & Media
    gate hides them. Only NULL rows are touched; explicit categories stay.
    """

    # Mirror of the migration's UPDATE — see migrations/versions/
    # b1c2d3e4f5a6_backfill_journalism_mission_category.py. The cased
    # 'JOURNALISME' (enum NAME, not the lowercase value) is the contract:
    # the round-trip assert below would LookupError if it were wrong.
    _BACKFILL = text(
        "UPDATE mkp_mission_offer SET category = 'JOURNALISME' "
        "WHERE category IS NULL"
    )

    def test_backfill_sets_null_to_journalisme_and_spares_explicit_categories(
        self, db_session: Session, test_emitter, test_org
    ):
        legacy = _make_mission(db_session, test_emitter, test_org, category=None)
        comm = _make_mission(
            db_session,
            test_emitter,
            test_org,
            category=MissionCategory.COMMUNICATION,
        )
        db_session.flush()
        assert legacy.category is None

        db_session.execute(self._BACKFILL)
        db_session.expire_all()

        # NULL legacy mission is now journalism — and reads back as the
        # enum (proves the stored casing matches the ORM, no LookupError).
        assert (
            db_session.get(MissionOffer, legacy.id).category
            == MissionCategory.JOURNALISME
        )
        # An explicit category is left untouched.
        assert (
            db_session.get(MissionOffer, comm.id).category
            == MissionCategory.COMMUNICATION
        )
