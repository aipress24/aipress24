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


def _make_user(db_session: Session, email: str = "events-pub@example.com") -> User:
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
        email=email,
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
    # Un événement à venir : `arrow.now()` en date de début le rendrait
    # instantanément clos aux demandes (RG-04), ce qu'aucun de ces
    # tests ne cherche à vérifier.
    today = arrow.now().shift(days=2)
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
    client_org = Organisation(name="Fake-Davi Logistique", bw_name="Davi Logistique")
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


def test_event_detail_shows_accreditation_button_for_journalist(
    app: Flask,
    db_session: Session,
):
    """Ticket #0138b (Erick, 2026-05-17): on the event detail page,
    a journalist must see the accreditation button. Erick reported that
    for a delegated event (PR agency publishing for a client) the button
    was missing entirely.

    The label is « Demande d'accréditation » since lot L2 (EVT-42): the
    member asks and the organiser decides, where the button used to
    grant accreditation outright. The regression this pins is unchanged
    — a journalist must be offered a way to ask.

    **L'événement appartient à quelqu'un d'autre**, et c'est le sujet :
    #0138b parle d'un journaliste devant l'annonce d'un tiers. Le
    montage réutilisait le lecteur comme propriétaire par commodité, si
    bien qu'il a viré au rouge quand #0319 a cessé de proposer le bouton
    à l'organisateur — un défaut de fixture, pas de règle. Le pendant,
    « l'organisateur ne le voit pas », est couvert par
    `e2e_playwright/regressions/test_bugs_0319_0325.py`.
    """
    user = _make_user(db_session)
    organiser = _make_user(db_session, email="events-organiser@example.com")
    agency = Organisation(name="Fake-Les Propulseurs PR")
    client_org = Organisation(name="Fake-Davi Logistique", bw_name="Davi Logistique")
    db_session.add_all([agency, client_org])
    db_session.flush()
    user.organisation = agency
    db_session.flush()
    event = _make_event_with_publisher(db_session, organiser.id, client_org)

    client = make_authenticated_client(app, user)
    response = client.get(f"/events/{event.id}", follow_redirects=True)
    assert response.status_code == 200
    html = response.data.decode()
    # Le geste, et pas seulement le mot : `hx-vals` est ce que le bouton
    # *fait*. La forme précédente cherchait « Demande d&#39;accréditation »
    # — une apostrophe échappée que le rendu ne produit pas, le texte
    # littéral d'un gabarit n'étant pas échappé — puis retombait sur
    # « accréditation », présent ailleurs dans la page. Elle passait donc
    # sans jamais voir le bouton.
    assert '"action": "request-accreditation"' in html, (
        "the accreditation button must be visible to journalists on "
        "the event detail (#0138b)"
    )
    assert "Demande d'accréditation" in html, "…and it must carry its label (EVT-42)"


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


def test_a_cancelled_event_is_listed_with_its_banner(
    app: Flask,
    db_session: Session,
):
    """ANN-04 — sur la liste publique, l'annonce reste, barrée.

    Le bandeau se lit sur `EventPost.cancelled_at` et non sur une clé
    calculée par `EventListVM` : la même carte est rendue sur le
    Business Wall d'une organisation à partir de la ligne brute, où les
    clés du view model sont absentes. C'est ce qui a fait que la
    pastille « Accrédité.e » n'y apparaît toujours pas.
    """
    user = _make_user(db_session)
    publisher = Organisation(name="Fake-Salon annulé", bw_name="SA")
    db_session.add(publisher)
    db_session.flush()
    event = _make_event_with_publisher(db_session, user.id, publisher)
    event.cancelled_at = arrow.utcnow()
    event.cancellation_reason = "Grève des transports"
    db_session.flush()

    client = make_authenticated_client(app, user)
    body = client.get("/events/", follow_redirects=True).data.decode()

    assert f'href="/events/{event.id}"' in body, "ANN-04 — toujours listé"
    assert "Événement annulé" in body
    assert "Grève des transports" in body
    assert "line-through" in body
