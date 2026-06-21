# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression: GET /wire/tab/wall must not N+1.

It used to fire ~90 SQL queries — per card it loaded the « vues » counter
(2 queries), the author's organisation, profile (job title), roles (avatar
border), the publisher org, and the polymorphic subclass columns. All are
now batched / eager-loaded, so the query count is flat regardless of how
many cards (or how many distinct authors/publishers) the wall shows.
"""

from __future__ import annotations

import arrow
from sqlalchemy import event

from app.enums import RoleEnum
from app.flask.extensions import db
from app.models.auth import KYCProfile, Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wire.models import ArticlePost
from tests.c_e2e.conftest import make_authenticated_client


def _press_role(session) -> Role:
    role = session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if role is None:
        role = Role(name=RoleEnum.PRESS_MEDIA.name, description="press")
        session.add(role)
        session.flush()
    return role


def _make_author(session, role: Role, i: int) -> User:
    org = Organisation(name=f"Author Org {i}")
    session.add(org)
    session.flush()
    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {}
    user = User(
        email=f"perf_author_{i}@example.com",
        active=True,
        first_name=f"A{i}",
        last_name="X",
    )
    user.photo = b""
    user.organisation = org
    user.roles.append(role)
    user.profile = profile
    session.add_all([user, profile])
    session.flush()
    return user


def _seed_wall(session, n_articles: int) -> User:
    """Seed a wall where every article has a DISTINCT author (org + profile
    + roles) and a DISTINCT publisher — the shape that surfaces the per-card
    N+1s (a single shared author/publisher hides them via the identity map)."""
    role = _press_role(session)
    viewer = _make_author(session, role, 0)  # the logged-in reader
    for i in range(1, n_articles + 1):
        author = _make_author(session, role, i)
        publisher = Organisation(name=f"Media {i}")
        session.add(publisher)
        session.flush()
        session.add(
            ArticlePost(
                title=f"Wall perf {i}",
                content=f"Body {i}",
                status=PublicationStatus.PUBLIC,
                owner=author,
                publisher=publisher,
                published_at=arrow.now().shift(minutes=-i),
                # A real cover image : the card renders its URL (no query),
                # not a per-card carousel that loads the newsroom blobs.
                newsroom_id=1000 + i,
                image_id=2000 + i,
            )
        )
    session.commit()
    return viewer


def test_wall_render_is_not_n_plus_one(app, db_session):
    viewer = _seed_wall(db_session, n_articles=12)
    client = make_authenticated_client(app, viewer)

    statements: list[str] = []

    def _capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", _capture)
    try:
        response = client.get("/wire/tab/wall")
    finally:
        event.remove(db.engine, "before_cursor_execute", _capture)

    assert response.status_code == 200
    n = len(statements)
    # 12 cards, each with a distinct author + publisher. Everything is
    # batch-loaded, so the count is flat. A reintroduced per-card N+1 (org,
    # profile, roles, publisher, consultation count, subclass columns) would
    # add ≥12 here and trip this bound.
    assert n < 20, f"{n} SQL queries rendering the wall:\n" + "\n".join(statements)
