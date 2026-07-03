# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""The public content-detail pages must not serve non-public content.

`/wire/<id>` and `/events/<id>` used to fetch by bare id, so a DRAFT /
unpublished / taken-down post was served to anyone by direct URL. The
`get_public_obj` gate now 404s a non-public row for everyone except its
owner (and admins) — access parity with the portal listings.
"""

from __future__ import annotations

import arrow
from flask import Flask
from sqlalchemy.orm import Session

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.events.models import EventPost
from app.modules.wire.models import ArticlePost
from tests.c_e2e.conftest import make_authenticated_client


def _setup(db_session: Session) -> tuple[User, User, Organisation]:
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    org = Organisation(name="Gate Org")
    author = User(email="gate-author@example.com", active=True)
    reader = User(email="gate-reader@example.com", active=True)
    author.organisation = org
    author.roles.append(role)
    reader.roles.append(role)
    db_session.add_all([role, org, author, reader])
    db_session.flush()
    return author, reader, org


def test_wire_detail_gates_non_public_articles(app: Flask, db_session: Session) -> None:
    author, reader, org = _setup(db_session)
    common = {
        "owner": author,
        "publisher_id": org.id,
        "content": "<p>body</p>",
        "summary": "s",
    }
    public = ArticlePost(
        title="Public",
        status=PublicationStatus.PUBLIC,
        published_at=arrow.utcnow(),
        **common,
    )
    draft = ArticlePost(title="Secret draft", status=PublicationStatus.DRAFT, **common)
    db_session.add_all([public, draft])
    db_session.commit()

    # make_authenticated_client can't hold two identities at once, so run the
    # reader's requests before creating the author's client.
    reader_client = make_authenticated_client(app, reader)
    # Public article: served to anyone.
    assert reader_client.get(f"/wire/{public.id}").status_code == 200
    # Draft: 404 for a non-owner (leak closed).
    assert reader_client.get(f"/wire/{draft.id}").status_code == 404

    # Draft: still reachable by its own author (access parity).
    author_client = make_authenticated_client(app, author)
    assert author_client.get(f"/wire/{draft.id}").status_code == 200


def test_events_detail_gates_non_public_events(app: Flask, db_session: Session) -> None:
    author, reader, org = _setup(db_session)
    public = EventPost(
        owner=author,
        publisher_id=org.id,
        title="Public event",
        content="<p>e</p>",
        summary="s",
        status=PublicationStatus.PUBLIC,
        published_at=arrow.utcnow(),
    )
    draft = EventPost(
        owner=author,
        publisher_id=org.id,
        title="Draft event",
        content="<p>e</p>",
        summary="s",
        status=PublicationStatus.DRAFT,
    )
    db_session.add_all([public, draft])
    db_session.commit()

    reader_client = make_authenticated_client(app, reader)

    assert reader_client.get(f"/events/{public.id}").status_code == 200
    assert reader_client.get(f"/events/{draft.id}").status_code == 404
