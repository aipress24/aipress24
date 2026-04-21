# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for the press-releases clause used by swork/views/organisation.

Press releases must appear on:
1. the emitter organisation's Business Wall (direct publisher); and
2. the Business Wall of the PR agency whose user posted on its behalf.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.flask.extensions import db
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.swork.views.organisation import _press_releases_for_org_clause
from app.modules.wire.models import PressReleasePost

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _make_user_in_org(db_session: Session, org: Organisation, name: str) -> User:
    user = User(
        email=f"{name.lower()}-{uuid.uuid4().hex[:6]}@example.com",
        first_name=name,
        last_name="Test",
        active=True,
    )
    user.organisation = org
    user.organisation_id = org.id
    db_session.add(user)
    db_session.flush()
    return user


def _make_press_release(
    db_session: Session,
    owner: User,
    publisher_org_id: int,
    title: str = "PR",
) -> PressReleasePost:
    post = PressReleasePost()
    post.title = title
    post.owner_id = owner.id
    post.publisher_id = publisher_org_id
    post.status = PublicationStatus.PUBLIC  # type: ignore[assignment]
    db_session.add(post)
    db_session.flush()
    return post


def _count_for_org(org: Organisation) -> int:
    stmt = (
        select(func.count())
        .select_from(PressReleasePost)
        .where(_press_releases_for_org_clause(org.id))
        .where(PressReleasePost.status == PublicationStatus.PUBLIC)
    )
    return db.session.execute(stmt).scalar() or 0


def _fetch_for_org(org: Organisation) -> list[PressReleasePost]:
    stmt = (
        select(PressReleasePost)
        .where(_press_releases_for_org_clause(org.id))
        .where(PressReleasePost.status == PublicationStatus.PUBLIC)
    )
    return list(db.session.execute(stmt).scalars())


class TestEmitterVisibility:
    def test_emitter_sees_its_own_press_release(self, db_session: Session):
        emitter_org = Organisation(name=f"Emitter-{uuid.uuid4().hex[:6]}")
        db_session.add(emitter_org)
        db_session.flush()
        owner = _make_user_in_org(db_session, emitter_org, "EmitterUser")

        _make_press_release(
            db_session, owner, emitter_org.id, title="Our own PR"
        )

        posts = _fetch_for_org(emitter_org)

        assert [p.title for p in posts] == ["Our own PR"]

    def test_emitter_does_not_see_unrelated_press_releases(
        self, db_session: Session
    ):
        emitter_org = Organisation(name=f"Emitter2-{uuid.uuid4().hex[:6]}")
        other_org = Organisation(name=f"Other-{uuid.uuid4().hex[:6]}")
        db_session.add_all([emitter_org, other_org])
        db_session.flush()
        other_owner = _make_user_in_org(db_session, other_org, "OtherUser")

        _make_press_release(
            db_session, other_owner, other_org.id, title="Unrelated"
        )

        assert _count_for_org(emitter_org) == 0


class TestAgencyRepresentingClientVisibility:
    """When an agency's user publishes a PR attributed to a client, it must
    appear on the agency's BW (as well as the client's BW)."""

    def test_agency_bw_shows_pr_published_for_client(
        self, db_session: Session
    ):
        agency_org = Organisation(name=f"Agency-{uuid.uuid4().hex[:6]}")
        client_org = Organisation(name=f"Client-{uuid.uuid4().hex[:6]}")
        db_session.add_all([agency_org, client_org])
        db_session.flush()

        agency_user = _make_user_in_org(db_session, agency_org, "AgencyUser")
        _make_press_release(
            db_session, agency_user, client_org.id, title="For client"
        )

        agency_titles = {p.title for p in _fetch_for_org(agency_org)}
        client_titles = {p.title for p in _fetch_for_org(client_org)}

        assert "For client" in agency_titles
        assert "For client" in client_titles

    def test_unrelated_org_does_not_see_agency_published_pr(
        self, db_session: Session
    ):
        agency_org = Organisation(name=f"AgencyU-{uuid.uuid4().hex[:6]}")
        client_org = Organisation(name=f"ClientU-{uuid.uuid4().hex[:6]}")
        stranger_org = Organisation(name=f"StrangerU-{uuid.uuid4().hex[:6]}")
        db_session.add_all([agency_org, client_org, stranger_org])
        db_session.flush()

        agency_user = _make_user_in_org(db_session, agency_org, "AgencyU")
        _make_press_release(
            db_session, agency_user, client_org.id, title="Cross-publish"
        )

        assert _count_for_org(stranger_org) == 0

    def test_no_duplicate_when_agency_publishes_for_itself(
        self, db_session: Session
    ):
        """If publisher_id == owner's org_id, the OR must not double-count."""
        agency_org = Organisation(name=f"SelfPub-{uuid.uuid4().hex[:6]}")
        db_session.add(agency_org)
        db_session.flush()
        user = _make_user_in_org(db_session, agency_org, "Self")

        _make_press_release(
            db_session, user, agency_org.id, title="Self-published"
        )

        assert _count_for_org(agency_org) == 1

    def test_draft_press_releases_are_excluded(self, db_session: Session):
        agency_org = Organisation(name=f"Draft-{uuid.uuid4().hex[:6]}")
        client_org = Organisation(name=f"DraftClient-{uuid.uuid4().hex[:6]}")
        db_session.add_all([agency_org, client_org])
        db_session.flush()
        user = _make_user_in_org(db_session, agency_org, "Drafter")

        post = _make_press_release(
            db_session, user, client_org.id, title="Draft PR"
        )
        post.status = PublicationStatus.DRAFT  # type: ignore[assignment]
        db_session.flush()

        assert _count_for_org(agency_org) == 0
        assert _count_for_org(client_org) == 0
