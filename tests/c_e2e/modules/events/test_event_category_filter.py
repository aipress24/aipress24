# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The event family: the chip, the link, the filter — 2026-09-02.

`Event` had five subclasses, each carrying a `Meta.type_label`
("Presse", "Salons/Colloques"…), and the card turned it into a green
pill whose `type_id` fed `hx-vals='{"force-tab": …}'`: clicking narrowed
the list to that type. Flattening everything into a single `EventPost`
took the subclasses with it; `get_meta_attr` returned `""`, and all that
remained was an empty green oval on every card.

The notion had survived one step further along — the five subclasses
became the five families of the `events` taxonomy, and
`EventPost.category` holds the normalised form. These tests cover what
replaces it: a chip carrying the family, a **link** to the other events
of the same family, and a filter that is visible and removable.
"""

from __future__ import annotations

import arrow
import pytest
from bs4 import BeautifulSoup
from flask import request

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.events.event_receiver import event_type_to_category
from app.modules.events.models import EventPost
from app.modules.events.views.events_list import _category_label, _url_without
from tests.c_e2e.conftest import make_authenticated_client


def _make_event(db_session, owner, title: str, genre: str) -> EventPost:
    start = arrow.now().shift(days=2)
    event = EventPost(
        title=title,
        summary="Summary.",
        owner_id=owner.id,
        status=PublicationStatus.PUBLIC,
        start_datetime=start,
        end_datetime=start.shift(hours=1),
        genre=genre,
        category=event_type_to_category(genre),
        sector="Industrie / Télécommunications & internet",
    )
    db_session.add(event)
    db_session.flush()
    return event


@pytest.fixture
def two_families(app, db_session):
    """One Press event, one Business event, and a client."""
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if role is None:
        role = Role(
            name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value
        )
        db_session.add(role)
        db_session.flush()

    org = Organisation(name="Fake-Agence Capri")
    db_session.add(org)
    db_session.flush()
    user = User(email="famille@example.com", first_name="Babette", last_name="Lemir")
    user.photo = b""
    user.active = True
    user.organisation = org
    user.profile = KYCProfile(match_making={"fonctions_journalisme": ["Journaliste"]})
    user.roles.append(role)
    db_session.add(user)
    db_session.flush()

    press = _make_event(db_session, user, "A press briefing", "Press / Point presse")
    show = _make_event(
        db_session, user, "A trade show", "Business / Salon professionnel"
    )
    return make_authenticated_client(app, user), press, show


def test_the_chip_carries_the_family_and_points_at_its_own(two_families) -> None:
    """A link, not an `hx-post`: the card is also rendered on an
    organisation's Business Wall, which has no `#content` — which is
    exactly what made the original pill inert (#0138)."""
    client, _press, _show = two_families

    html = client.get("/events/", follow_redirects=True).data.decode()
    chips = BeautifulSoup(html, "html.parser").select("li.card .chip")
    families = {c.get_text(strip=True): c for c in chips}

    assert "Press" in families, f"the family is missing: {list(families)}"
    assert "Business" in families

    link = families["Press"]
    assert link.name == "a", "the chip must be a link"
    assert link["href"].endswith("/events/?category=press"), link["href"]


def test_the_link_keeps_only_its_family(two_families) -> None:
    """The real use: the list actually narrows."""
    client, press, show = two_families

    html = client.get("/events/?category=press", follow_redirects=True).data.decode()

    assert press.title in html
    assert show.title not in html, "the filter lets other families through"


def test_the_active_filter_is_visible_and_removable(two_families) -> None:
    """A filter you cannot see is a filter you cannot remove. It clears
    with a link, not with the others' `hx-post`: it lives in the URL and
    not in the session."""
    client, _press, _show = two_families

    html = client.get("/events/?category=press", follow_redirects=True).data.decode()
    soup = BeautifulSoup(html, "html.parser")
    clear = soup.select_one('a[aria-label^="Retirer le filtre"]')

    assert clear is not None, "no way to remove the family filter"
    # The label, not the stored form: "Press", not "press".
    assert "type : Press" in clear.parent.get_text()
    assert "category" not in clear["href"], clear["href"]


def test_clearing_the_family_keeps_the_search(two_families) -> None:
    """A bare return to `/events/` would wipe the current search."""
    client, _press, _show = two_families

    html = client.get(
        "/events/?category=press&search=press", follow_redirects=True
    ).data.decode()
    clear = BeautifulSoup(html, "html.parser").select_one(
        'a[aria-label^="Retirer le filtre"]'
    )

    assert clear is not None, "no way to remove the family filter"
    assert "search=press" in clear["href"], clear["href"]


class TestTheFamilyLabel:
    """ "press" is a stored form, not a label."""

    def test_recovers_the_case_of_the_real_families(self) -> None:
        assert _category_label("press") == "Press"
        assert _category_label("business") == "Business"

    def test_underscores_become_spaces_again(self) -> None:
        """`event_type_to_category` is what put them there."""
        assert _category_label("arts_du_spectacle") == "Arts du spectacle"

    def test_nothing_gives_nothing(self) -> None:
        assert _category_label("") == ""


class TestTheUrlWithoutOneParameter:
    def test_drops_the_targeted_parameter(self, app) -> None:
        with app.test_request_context("/events/?category=press&search=x"):
            url = _url_without(request.args, "category")

        assert "category" not in url
        assert "search=x" in url

    def test_keeps_the_others_as_they_were(self, app) -> None:
        with app.test_request_context("/events/?search=x&month=2026-09"):
            url = _url_without(request.args, "category")

        assert "search=x" in url
        assert "month=2026-09" in url
