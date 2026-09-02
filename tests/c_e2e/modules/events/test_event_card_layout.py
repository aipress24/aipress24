# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Event-card layout — audit 2026-09-02.

Two defects that "the page returns 200" cannot see, both readable in the
DOM:

- a dead block left commented out had swallowed a **live** `</div>`. The
  browser closed at `</li>`, so the summary, the chips, the author and
  the card footer ended up nested inside the header, 16px too far right
  — the date and the title alone stayed at the correct margin;
- `.chip` is an `inline-flex` with padding: an empty value did not
  render "nothing" there but a bare coloured pill, and `type_label`
  defaults to `""`.
"""

from __future__ import annotations

import arrow
import pytest
from bs4 import BeautifulSoup

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.events.models import EventPost
from tests.c_e2e.conftest import make_authenticated_client


@pytest.fixture
def card(app, db_session):
    """A public event's card, as /events/ renders it."""
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if role is None:
        role = Role(
            name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value
        )
        db_session.add(role)
        db_session.flush()

    org = Organisation(name="Fake-Agence Capri", bw_name="Fake-Agence Capri RP")
    db_session.add(org)
    db_session.flush()

    user = User(
        email="card-layout@example.com", first_name="Babette", last_name="Lemir"
    )
    user.photo = b""
    user.active = True
    user.organisation = org
    user.profile = KYCProfile(match_making={"fonctions_journalisme": ["Journaliste"]})
    user.roles.append(role)
    db_session.add(user)
    db_session.flush()

    start = arrow.now().shift(days=2)
    event = EventPost(
        title="Invitation Phneider Electric",
        summary="A l'occasion de la 9ème édition du Sommet.",
        owner_id=user.id,
        publisher_id=org.id,
        status=PublicationStatus.PUBLIC,
        start_datetime=start,
        end_datetime=start.shift(hours=1),
        category="press",
        # `type_label` is left unset: that is the common case, and the
        # one that produced the empty green oval.
        sector="Industrie / Télécommunications & internet",
    )
    db_session.add(event)
    db_session.flush()

    client = make_authenticated_client(app, user)
    html = client.get("/events/", follow_redirects=True).data.decode()
    li = BeautifulSoup(html, "html.parser").select_one("li.card")
    assert li is not None, "no event card on /events/"
    return li


def test_the_sections_are_siblings_not_nested(card) -> None:
    """The real symptom: a `</div>` carried off by a comment.

    The chips, the author and the footer belonged to the header rather
    than to the card. We assert on structure and not on pixels: nesting
    is what shifts them, the margin is only its consequence.
    """
    header = card.select_one("div.pt-4")
    assert header is not None

    for selector, what in (
        (".chip", "the chips"),
        ("hr", "the rules"),
        ("button[hx-vals]", "the like button"),
    ):
        found = card.select(selector)
        assert found, f"{what}: missing from the card"
        for element in found:
            assert element not in header.descendants, (
                f"{what}: nested in the header instead of being a sibling — "
                "a `</div>` is missing, and everything after the title "
                "shifts one notch to the right"
            )


def test_no_empty_chip(card) -> None:
    """A chip with no text is a bare coloured pill."""
    empty = [
        str(chip) for chip in card.select(".chip") if not chip.get_text(strip=True)
    ]
    assert not empty, f"empty chips — `.chip` has padding, they show: {empty}"


def test_the_expected_chips_are_there(card) -> None:
    """The guard must not swallow the chips that do have a value."""
    labels = {chip.get_text(strip=True) for chip in card.select(".chip")}

    assert "press" in labels
    # The sector is the leaf of "FAMILY / Detail", without the space
    # `split("/")[-1]` used to leave behind.
    assert "Télécommunications & internet" in labels
    assert "Pour : Fake-Agence Capri RP" in labels


def test_the_chip_row_has_a_gutter(card) -> None:
    """The spacing came from template whitespace, which disappears on
    wrap: two rows of chips touched."""
    row = card.select_one(".chip").parent

    assert "flex" in row["class"]
    assert "flex-wrap" in row["class"]
    assert any(c.startswith("gap-") for c in row["class"]), row["class"]
