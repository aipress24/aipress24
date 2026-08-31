# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Round-trip integration tests for ``events/models.py``.

Why this lives at the ``b_integration`` tier
--------------------------------------------
``EventPost`` is wired through SQLAlchemy's joined-table polymorphic
machinery: ``BaseContent`` declares ``polymorphic_on = type`` and
``EventPost`` derives its ``polymorphic_identity`` from
``to_snake_case(cls.__name__)``, with its own ``evt_event_post`` table
holding the FK back to ``cnt_base.id``.

That guarantee only holds against a real engine + session: insertion has
to populate ``cnt_base.type`` with the right discriminator, and
re-fetching through the base mapper has to instantiate the concrete
class. Pure unit tests with stubs would tell us nothing about it.

This file also pins the constraint and default-value contract by
flushing real rows and re-reading them — the mandatory ``owner`` FK on
the ``Owned`` mixin, the textual defaults of ``EventPostBase`` and of
the ``Addressable`` mixin, and ``EventPost``'s own.

*Historique.* Ce module couvrait aussi cinq classes sœurs —
``PublicEvent``, ``PressEvent``, ``TrainingEvent``, ``CultureEvent``,
``ContestEvent`` — supprimées au lot C0b (``ONG-03``) : rien ne les
instanciait et leurs tables étaient vides. Les deux tests qui n'avaient
de sens qu'avec plusieurs types concrets (non-collapse vers
``EventPost``, ségrégation d'une population mixte) ont disparu avec
elles ; les autres sont conservés sur ``EventPost`` seul.

Note: ``EventPost`` does NOT use a Taggable mixin —
``app.models.content.mixins.Tagged`` exists but is empty (``# TODO``)
and is not in ``EventPostBase``'s MRO. We do not test it here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.models.auth import User
from app.models.content.base import BaseContent
from app.modules.events.models import EventPost

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ----------------------------------------------------------------
# Fixtures — real rows, no mocks
# ----------------------------------------------------------------


@pytest.fixture
def owner(db_session: Session) -> User:
    """A real ``User`` row to satisfy the ``Owned`` mixin's NOT NULL FK."""
    u = User(email="event-owner@example.com")
    u.photo = b""
    u.active = True
    db_session.add(u)
    db_session.flush()
    return u


# Expected polymorphic identity (snake_case of the class name) per the
# ``BaseContent.get_type_id`` rule. Pinning these here means a rename
# of any subclass without a migration would break this test loudly —
# which is the intended canary.
EXPECTED_IDENTITY: dict[type, str] = {EventPost: "event_post"}


# ----------------------------------------------------------------
# Polymorphic identity round-trip
# ----------------------------------------------------------------


class TestPolymorphicIdentityRoundTrip:
    """Each subclass must round-trip through ``BaseContent``'s
    polymorphic mapper as its concrete type."""

    def test_type_discriminator_pins_to_snake_case(
        self, db_session: Session, owner: User
    ) -> None:
        row = EventPost(title="T-EventPost", owner=owner)
        db_session.add(row)
        db_session.flush()
        db_session.refresh(row)

        assert row.type == EXPECTED_IDENTITY[EventPost]

    def test_refetch_via_base_yields_concrete_subclass(
        self, db_session: Session, owner: User
    ) -> None:
        # Create via the concrete subclass.
        row = EventPost(title="R-EventPost", owner=owner)
        db_session.add(row)
        db_session.flush()
        row_id = row.id

        # Drop from identity map so the next query truly re-fetches.
        db_session.expunge(row)

        # Re-fetch via the *base* mapper — polymorphic loading must
        # pick the right concrete class from the discriminator column.
        fetched = db_session.execute(
            sa.select(BaseContent).where(BaseContent.id == row_id)
        ).scalar_one()

        assert type(fetched) is EventPost
        assert isinstance(fetched, EventPost.__mro__[1])  # EventPostBase


# ----------------------------------------------------------------
# Required FK constraint — owner must be present
# ----------------------------------------------------------------


class TestOwnerRequiredConstraint:
    """``Owned`` declares ``owner_id`` as NOT NULL — flush must reject
    a row without it for every concrete subclass."""

    def test_flush_without_owner_raises_integrity_error(
        self, db_session: Session
    ) -> None:
        row = EventPost(title="No owner")  # no owner / owner_id
        db_session.add(row)

        with pytest.raises(IntegrityError):
            db_session.flush()

        # Roll back the failed savepoint so the outer fixture transaction
        # can keep going. (The autouse ``db_session`` fixture restarts a
        # nested savepoint on the next ``after_transaction_end``.)
        db_session.rollback()


# ----------------------------------------------------------------
# Default-value pinning — flush + refresh
# ----------------------------------------------------------------


class TestDefaultValuesRoundTrip:
    """Defaults declared on ``EventPostBase`` / ``Addressable`` /
    ``EventPost`` must survive a flush + refresh cycle."""

    def test_eventpostbase_defaults_pin(self, db_session: Session, owner: User) -> None:
        row = EventPost(title="Defaults", owner=owner)
        db_session.add(row)
        db_session.flush()
        db_session.refresh(row)

        # From ``EventPostBase``.
        assert row.genre == ""
        assert row.sector == ""
        assert row.category == ""
        assert row.language == "FRE"
        assert row.logo_url == ""
        assert row.cover_image_url == ""
        assert row.location == ""
        # From ``BaseContent``.
        assert row.content == ""
        assert row.summary == ""
        assert row.url == ""
        # ``start_datetime`` / ``end_datetime`` are nullable and have no
        # default — they round-trip as None.
        assert row.start_datetime is None
        assert row.end_datetime is None

    def test_addressable_defaults_pin(self, db_session: Session, owner: User) -> None:
        row = EventPost(title="Addr", owner=owner)
        db_session.add(row)
        db_session.flush()
        db_session.refresh(row)

        # From the ``Addressable`` mixin.
        assert row.address == ""
        assert row.city == ""
        assert row.region == ""
        assert row.country == ""
        assert row.dept_code == ""
        assert row.region_code == ""
        assert row.zip_code == ""
        assert row.country_code == ""
        assert row.geo_lat == 0
        assert row.geo_lng == 0

    def test_eventpost_specific_defaults_pin(
        self, db_session: Session, owner: User
    ) -> None:
        # ``eventroom_id`` is nullable; the two ``pays_zip_ville*`` columns
        # default to empty string. Only ``EventPost`` (not its siblings)
        # declares these.
        row = EventPost(title="EP", owner=owner)
        db_session.add(row)
        db_session.flush()
        db_session.refresh(row)

        assert row.eventroom_id is None
        assert row.pays_zip_ville == ""
        assert row.pays_zip_ville_detail == ""
        # Hybrid properties derived from the empty detail.
        assert row.code_postal == ""
        assert row.departement == ""
        assert row.ville == ""

    def test_overrides_survive_round_trip(
        self, db_session: Session, owner: User
    ) -> None:
        # Explicit values must NOT be clobbered by defaults on flush.
        row = EventPost(
            title="Override",
            owner=owner,
            genre="forum",
            sector="tech",
            language="ENG",
            location="Paris",
        )
        db_session.add(row)
        db_session.flush()
        db_session.refresh(row)

        assert row.genre == "forum"
        assert row.sector == "tech"
        assert row.language == "ENG"
        assert row.location == "Paris"
