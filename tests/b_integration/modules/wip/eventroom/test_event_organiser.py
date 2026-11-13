# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""An event's organiser is an organisation its author may publish for.

The organiser's Business Wall lists the event, so naming one is
publishing on that wall. Any other organiser goes in the free text.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from flask import g
from werkzeug.exceptions import Forbidden

from app.enums import BWStatus
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.wip.crud.cbvs.events import EventsWipView
from app.modules.wip.models.eventroom.event import Event

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _org_with_bw(db_session: Session, owner: User) -> Organisation:
    org = Organisation(name=f"Org {uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()
    org.bw_id = bw.id
    db_session.flush()
    return org


@pytest.fixture
def author(db_session: Session) -> User:
    user = User(email=f"author-{uuid.uuid4().hex[:8]}@example.com", active=True)
    db_session.add(user)
    db_session.flush()
    user.organisation = _org_with_bw(db_session, user)
    db_session.flush()
    return user


@pytest.fixture
def stranger_org(db_session: Session) -> Organisation:
    owner = User(email=f"other-{uuid.uuid4().hex[:8]}@example.com", active=True)
    db_session.add(owner)
    db_session.flush()
    return _org_with_bw(db_session, owner)


def test_the_picker_offers_only_publishable_organisations(
    app: Flask, author: User, stranger_org: Organisation
) -> None:
    view = EventsWipView()
    with app.test_request_context():
        g.user = author
        form = view.form_class()
        view._make_media_choices(form)

    ids = {value for value, _label in form.organiser_id.choices}
    assert str(author.organisation_id) in ids
    assert str(stranger_org.id) not in ids


def test_saving_another_organisation_as_organiser_is_refused(
    app: Flask, db_session: Session, author: User, stranger_org: Organisation
) -> None:
    event = Event(owner=author, publisher=author.organisation)
    event.organiser_id = stranger_org.id
    db_session.add(event)
    db_session.flush()

    with app.test_request_context():
        g.user = author
        with pytest.raises(Forbidden):
            EventsWipView()._post_update_model(event)
