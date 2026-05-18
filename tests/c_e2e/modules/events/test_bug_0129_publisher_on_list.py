# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Bug 0129 (extended scope): the publishing client (BW name) must appear
on the public /events/ list cards AND on the right column of the event
detail page. The original ticket was about the form's "Publier pour"
field showing a raw FK id; that part shipped in commit 91a30033. The PO
replayed and reported that the client name still wasn't visible on the
public surfaces. This module covers those.

These tests need a properly logged-in client: events views redirect
unauthenticated users to /login, so we use `make_authenticated_client`
from the e2e conftest (which actually runs Flask-Login's `login_user`)
rather than the local `authenticated_client` fixture that only stamps a
few session keys.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.events.models import EventPost
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _make_user(db_session: Session) -> User:
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if role is None:
        role = Role(
            name=RoleEnum.PRESS_MEDIA.name,
            description=RoleEnum.PRESS_MEDIA.value,
        )
        db_session.add(role)
        db_session.flush()
    profile = KYCProfile(match_making={"fonctions_journalisme": ["Journaliste"]})
    user = User(
        email="events-pub@example.com",
        first_name="Pub",
        last_name="Tester",
    )
    user.photo = b""
    user.active = True
    user.profile = profile
    user.roles.append(role)
    db_session.add(user)
    db_session.flush()
    return user


def _make_event_with_publisher(
    db_session: Session, owner_id: int, publisher: Organisation
) -> EventPost:
    today = arrow.now()
    event = EventPost(
        title="Fête du Pain 2026",
        owner_id=owner_id,
        publisher_id=publisher.id,
        status=PublicationStatus.PUBLIC,
        start_datetime=today,
        end_datetime=today.shift(days=1),
        genre="Salon",
        sector="Agro",
    )
    db_session.add(event)
    db_session.flush()
    return event


def test_events_list_card_shows_publisher_bw_name(
    app: Flask,
    db_session: Session,
):
    user = _make_user(db_session)
    publisher = Organisation(name="Fake-Léonard Industries", bw_name="Léonard SA")
    db_session.add(publisher)
    db_session.flush()
    _make_event_with_publisher(db_session, user.id, publisher)

    client = make_authenticated_client(app, user)
    response = client.get("/events/", follow_redirects=True)
    assert response.status_code == 200
    html = response.data.decode()
    assert "Léonard SA" in html, "publisher.bw_name missing from /events/ list card"
    assert "Pour" in html


def test_events_list_card_falls_back_to_name(
    app: Flask,
    db_session: Session,
):
    user = _make_user(db_session)
    publisher = Organisation(name="Acme Corp", bw_name="")
    db_session.add(publisher)
    db_session.flush()
    _make_event_with_publisher(db_session, user.id, publisher)

    client = make_authenticated_client(app, user)
    response = client.get("/events/", follow_redirects=True)
    assert response.status_code == 200
    assert "Acme Corp" in response.data.decode()


def test_event_detail_aside_shows_publisher_bw_name(
    app: Flask,
    db_session: Session,
):
    user = _make_user(db_session)
    publisher = Organisation(name="Fake-Léonard Industries", bw_name="Léonard SA")
    db_session.add(publisher)
    db_session.flush()
    event = _make_event_with_publisher(db_session, user.id, publisher)

    client = make_authenticated_client(app, user)
    response = client.get(f"/events/{event.id}", follow_redirects=True)
    assert response.status_code == 200
    html = response.data.decode()
    assert "Léonard SA" in html, "publisher.bw_name missing from event detail aside"
    assert "Pour" in html


def test_event_shows_published_by_relation_when_cross_org(
    app: Flask,
    db_session: Session,
):
    """Bug #0129 extension — When the event author belongs to an agency
    and publishes for a client, the detail page should show:
    "Publié par <agency> en tant que contact presse de <client>".
    """
    user = _make_user(db_session)
    agency = Organisation(name="Fake-Les Propulseurs PR")
    client_org = Organisation(name="Fake-Davi Logistique", bw_name="Davi Logistique")
    db_session.add_all([agency, client_org])
    db_session.flush()

    # Author belongs to the PR agency
    user.organisation = agency
    db_session.flush()

    event = _make_event_with_publisher(db_session, user.id, client_org)

    client = make_authenticated_client(app, user)
    response = client.get(f"/events/{event.id}", follow_redirects=True)
    assert response.status_code == 200
    html = response.data.decode()
    assert (
        "Publié par Fake-Les Propulseurs PR en tant que contact presse de Fake-Davi Logistique"
        in html
    ), "missing 'Publié par X en tant que contact presse de Y' on event detail"


def test_delegated_event_list_card_drops_redundant_pour_chip(
    app: Flask,
    db_session: Session,
):
    """Bug #0138: in the delegated case the italic "Publié par … en
    tant que contact presse de …" line already names the client, so
    the "Pour : <client>" chip (#0129) is a redundant doublon on the
    card and must NOT be shown. The non-delegated #0129 behaviour
    (chip shown) is still covered by the tests above.
    """
    user = _make_user(db_session)
    agency = Organisation(name="Fake-Les Propulseurs PR")
    client_org = Organisation(
        name="Fake-Davi Logistique", bw_name="Davi Logistique"
    )
    db_session.add_all([agency, client_org])
    db_session.flush()
    user.organisation = agency
    db_session.flush()
    _make_event_with_publisher(db_session, user.id, client_org)

    client = make_authenticated_client(app, user)
    response = client.get("/events/", follow_redirects=True)
    assert response.status_code == 200
    html = response.data.decode()
    assert (
        "Publié par Fake-Les Propulseurs PR en tant que contact presse "
        "de Fake-Davi Logistique" in html
    )
    assert "Pour :" not in html, (
        "the redundant 'Pour : <client>' chip must be gone in the "
        "delegated case (#0138)"
    )


def test_event_card_type_badge_is_a_real_link_not_dead_chip(
    app: Flask,
    db_session: Session,
):
    """Bug #0138b: the event-card type badge used to be a dead
    affordance (`href="#"` + `hx-post="" hx-target="#content"` with no
    `force-tab` handler) — on the BW org page (no #content) clicking it
    did nothing, so the event never "developed". It is now a real link
    to the event detail. Guard: the dead htmx markers are gone and the
    badge points at the event.
    """
    user = _make_user(db_session)
    publisher = Organisation(name="Fake-Léonard Industries", bw_name="Léo")
    db_session.add(publisher)
    db_session.flush()
    event = _make_event_with_publisher(db_session, user.id, publisher)

    client = make_authenticated_client(app, user)
    body = client.get("/events/", follow_redirects=True).data.decode()

    # `force-tab` was unique to the dead chip (no handler anywhere) —
    # its absence proves the broken affordance is gone, without the
    # false positives of page-wide `#content` / `href="#"` chrome.
    assert "force-tab" not in body
    assert f'href="/events/{event.id}"' in body
    assert "chip ~positive @low" in body  # the (now-linked) type badge
