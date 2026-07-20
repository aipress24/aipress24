# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Bug 0246: the organisation page right column lists the marketplace
offers the org has published (missions / projects / jobs) and the newest
recruits of its Business Wall."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from flask import url_for

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.biz.models._offers import (
    ApplicationStatus,
    JobOffer,
    MissionOffer,
    OfferApplication,
    ProjectOffer,
)
from app.modules.bw.bw_activation.bw_invitation import revoke_user_role
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    InvitationStatus,
    RoleAssignment,
)
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.events.models import EventPost, participation_table
from app.modules.swork.views.organisation import OrgVM
from app.services.activity_stream import ActivityType, get_timeline, post_activity

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _user(db_session: Session) -> User:
    user = User(email=f"u-{uuid.uuid4().hex[:8]}@example.com", active=True)
    db_session.add(user)
    db_session.flush()
    return user


def _org_with_bw(db_session: Session, owner: User) -> tuple[Organisation, BusinessWall]:
    org = Organisation(name=f"Org {uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
        name=org.name,
    )
    db_session.add(bw)
    db_session.flush()
    org.bw_id = bw.id
    org.bw_active = bw.bw_type
    db_session.flush()
    return org, bw


class TestEmittedOffers:
    def test_lists_only_this_orgs_public_offers(self, app: Flask, db_session: Session):
        owner = _user(db_session)
        org, _bw = _org_with_bw(db_session, owner)
        other_org, _ = _org_with_bw(db_session, owner)

        db_session.add_all(
            [
                MissionOffer(
                    owner=owner,
                    title="Ma mission",
                    status=PublicationStatus.PUBLIC,
                    emitter_org_id=org.id,
                ),
                MissionOffer(
                    owner=owner,
                    title="Brouillon",
                    status=PublicationStatus.DRAFT,
                    emitter_org_id=org.id,
                ),
                MissionOffer(
                    owner=owner,
                    title="Autre org",
                    status=PublicationStatus.PUBLIC,
                    emitter_org_id=other_org.id,
                ),
                ProjectOffer(
                    owner=owner,
                    title="Mon projet",
                    status=PublicationStatus.PUBLIC,
                    emitter_org_id=org.id,
                ),
                JobOffer(
                    owner=owner,
                    title="Mon offre",
                    status=PublicationStatus.PUBLIC,
                    emitter_org_id=org.id,
                ),
            ]
        )
        db_session.flush()

        with app.test_request_context():
            vm = OrgVM(org)
            assert [m.title for m in vm.get_missions_emises()] == ["Ma mission"]
            assert [p.title for p in vm.get_projets_emis()] == ["Mon projet"]
            assert [j.title for j in vm.get_jobs_emis()] == ["Mon offre"]


class TestOfferDetailEndpoints:
    """Pin the exact endpoint names the aside template hardcodes in its
    `url_for(...)` calls — a typo there would 500 the whole org page."""

    def test_endpoints_build(self, app: Flask):
        with app.test_request_context():
            assert url_for("biz.missions_detail", id=1)
            assert url_for("biz.projects_detail", id=1)
            assert url_for("biz.jobs_detail", id=1)


class TestNouvellesRecrues:
    def test_lists_accepted_members_excluding_owner(
        self, app: Flask, db_session: Session
    ):
        owner = _user(db_session)
        recruit = _user(db_session)
        pending = _user(db_session)
        org, bw = _org_with_bw(db_session, owner)

        db_session.add_all(
            [
                RoleAssignment(
                    business_wall_id=bw.id,
                    user_id=recruit.id,
                    role_type="BWMi",
                    invitation_status=InvitationStatus.ACCEPTED.value,
                    accepted_at=datetime.now(UTC),
                ),
                # A still-pending invitation must not count as a recruit.
                RoleAssignment(
                    business_wall_id=bw.id,
                    user_id=pending.id,
                    role_type="BWMi",
                    invitation_status=InvitationStatus.PENDING.value,
                ),
            ]
        )
        db_session.flush()

        with app.test_request_context():
            vm = OrgVM(org)
            ids = {u.id for u in vm.get_nouvelles_recrues()}

        assert recruit.id in ids
        assert owner.id not in ids, "the BW owner is not a « recrue »"
        assert pending.id not in ids, "a pending invitation is not yet a recruit"


class TestEventsParticipes:
    def test_lists_events_where_a_bw_member_participates(
        self, app: Flask, db_session: Session
    ):
        owner = _user(db_session)
        member = _user(db_session)
        outsider = _user(db_session)
        org, bw = _org_with_bw(db_session, owner)
        db_session.add(
            RoleAssignment(
                business_wall_id=bw.id,
                user_id=member.id,
                role_type="BWMi",
                invitation_status=InvitationStatus.ACCEPTED.value,
                accepted_at=datetime.now(UTC),
            )
        )
        db_session.flush()

        joined = EventPost(
            title="Salon de la presse",
            content="x",
            owner=owner,
            status=PublicationStatus.PUBLIC,
        )
        elsewhere = EventPost(
            title="Événement d'un tiers",
            content="x",
            owner=owner,
            status=PublicationStatus.PUBLIC,
        )
        db_session.add_all([joined, elsewhere])
        db_session.flush()
        # A BW member takes part in `joined`; a non-member in `elsewhere`.
        db_session.execute(
            sa.insert(participation_table).values(user_id=member.id, event_id=joined.id)
        )
        db_session.execute(
            sa.insert(participation_table).values(
                user_id=outsider.id, event_id=elsewhere.id
            )
        )
        db_session.flush()

        with app.test_request_context():
            titles = {e.title for e in OrgVM(org).get_events_participes()}

        assert "Salon de la presse" in titles
        assert "Événement d'un tiers" not in titles


class TestOffersWon:
    def test_lists_missions_won_by_a_bw_member(self, app: Flask, db_session: Session):
        owner = _user(db_session)
        member = _user(db_session)
        other_owner = _user(db_session)
        org, bw = _org_with_bw(db_session, owner)
        emitter_org, _ = _org_with_bw(db_session, other_owner)
        db_session.add(
            RoleAssignment(
                business_wall_id=bw.id,
                user_id=member.id,
                role_type="BWMi",
                invitation_status=InvitationStatus.ACCEPTED.value,
                accepted_at=datetime.now(UTC),
            )
        )
        db_session.flush()

        won = MissionOffer(
            owner=other_owner,
            title="Mission gagnée",
            status=PublicationStatus.PUBLIC,
            emitter_org_id=emitter_org.id,
        )
        lost = MissionOffer(
            owner=other_owner,
            title="Mission perdue",
            status=PublicationStatus.PUBLIC,
            emitter_org_id=emitter_org.id,
        )
        db_session.add_all([won, lost])
        db_session.flush()
        db_session.add_all(
            [
                OfferApplication(
                    offer_id=won.id,
                    owner_id=member.id,
                    status=ApplicationStatus.SELECTED,
                ),
                OfferApplication(
                    offer_id=lost.id,
                    owner_id=member.id,
                    status=ApplicationStatus.PENDING,
                ),
            ]
        )
        db_session.flush()

        with app.test_request_context():
            titles = {m.title for m in OrgVM(org).get_missions_remportees()}

        assert "Mission gagnée" in titles
        assert "Mission perdue" not in titles, "a PENDING application is not a win"


class TestDeparts:
    def test_revoked_member_is_recorded_as_a_depart(
        self, app: Flask, db_session: Session
    ):
        owner = _user(db_session)
        member = _user(db_session)
        org, bw = _org_with_bw(db_session, owner)
        db_session.add(
            RoleAssignment(
                business_wall_id=bw.id,
                user_id=member.id,
                role_type=BWRoleType.BWMI.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
                accepted_at=datetime.now(UTC),
            )
        )
        db_session.flush()
        db_session.refresh(bw)  # so `bw.role_assignments` sees the new row

        with app.test_request_context():
            assert revoke_user_role(bw, member, BWRoleType.BWMI) is True
            db_session.flush()
            names = {a.actor_name for a in OrgVM(org).get_departs()}

        assert member.name in names

    def test_departure_activity_does_not_break_the_org_timeline(
        self, app: Flask, db_session: Session
    ):
        """Regression: `_get_msg` raises on any (verb, object-type) it does
        not know, and `get_timeline(object=org)` runs it for every row — so a
        Leave-on-Organisation activity must have a message case."""
        owner = _user(db_session)
        member = _user(db_session)
        org, _bw = _org_with_bw(db_session, owner)

        with app.test_request_context():
            post_activity(ActivityType.Leave, member, org)
            db_session.flush()
            timeline = get_timeline(object=org)

        messages = [msg for _activity, msg in timeline]
        assert any("a quitté le Business Wall" in m for m in messages)
