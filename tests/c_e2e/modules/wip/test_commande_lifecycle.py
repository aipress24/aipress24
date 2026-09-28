# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0362 — the life of a commande.

Whoever placed it (its owner, a rédac chef or equivalent) edits,
validates, cancels and deletes it. Validating or cancelling it notifies
its destinataire, the journalist who will write it, by bell and by mail.
The destinataire only reads it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from app.flask.extensions import db
from app.flask.routing import url_for
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models import Commande
from app.services.emails import CommandeStatusNotificationMail
from app.services.notifications._models import Notification
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask

    from app.models.organisation import Organisation


@pytest.fixture
def journalist(fresh_db) -> User:
    """The destinataire, when `test_user` places the commande."""
    user = User(
        email=f"journaliste-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Aïcha",
        last_name="Benmahfoud",
        active=True,
    )
    fresh_db.session.add(user)
    fresh_db.session.commit()
    return user


@pytest.fixture
def sent_mails(monkeypatch) -> list[CommandeStatusNotificationMail]:
    sent: list[CommandeStatusNotificationMail] = []

    def record(mail: CommandeStatusNotificationMail) -> None:
        sent.append(mail)

    monkeypatch.setattr(CommandeStatusNotificationMail, "send", record)
    return sent


def _commande(
    fresh_db,
    *,
    owner: User,
    destinataire: User | None,
    org: Organisation,
    status: PublicationStatus = PublicationStatus.DRAFT,
) -> Commande:
    now = datetime.now(UTC)
    commande = Commande(
        titre="Le spatial européen",
        contenu="<p>Brief.</p>",
        owner_id=owner.id,
        commanditaire_id=owner.id,
        destinataire_id=destinataire.id if destinataire else None,
        media_id=org.id,
        status=status,
        date_limite_validite=now,
        date_bouclage=now,
        date_parution_prevue=now,
    )
    fresh_db.session.add(commande)
    fresh_db.session.commit()
    return commande


def _status_of(commande_id: int) -> PublicationStatus:
    db.session.remove()
    commande = db.session.get(Commande, commande_id)
    assert commande is not None
    return commande.status


class TestTheOwnerRunsIt:
    def test_validating_notifies_the_destinataire(
        self,
        app: Flask,
        fresh_db,
        test_user: User,
        journalist: User,
        test_org: Organisation,
        sent_mails: list[CommandeStatusNotificationMail],
    ) -> None:
        commande = _commande(
            fresh_db, owner=test_user, destinataire=journalist, org=test_org
        )
        journalist_id, journalist_email = journalist.id, journalist.email
        client = make_authenticated_client(app, test_user)

        response = client.get(url_for("CommandesWipView:validate", id=commande.id))

        assert response.status_code in {302, 303}
        assert _status_of(commande.id) == PublicationStatus.ACCEPTED
        bells = db.session.query(Notification).filter_by(receiver_id=journalist_id)
        assert any("validée" in bell.message for bell in bells)
        assert [mail.recipient for mail in sent_mails] == [journalist_email]

    def test_a_commande_without_destinataire_stays_a_draft(
        self,
        app: Flask,
        fresh_db,
        test_user: User,
        test_org: Organisation,
        sent_mails: list[CommandeStatusNotificationMail],
    ) -> None:
        commande = _commande(fresh_db, owner=test_user, destinataire=None, org=test_org)
        client = make_authenticated_client(app, test_user)

        client.get(url_for("CommandesWipView:validate", id=commande.id))

        assert _status_of(commande.id) == PublicationStatus.DRAFT
        assert sent_mails == []

    def test_cancelling_notifies_the_destinataire(
        self,
        app: Flask,
        fresh_db,
        test_user: User,
        journalist: User,
        test_org: Organisation,
        sent_mails: list[CommandeStatusNotificationMail],
    ) -> None:
        commande = _commande(
            fresh_db,
            owner=test_user,
            destinataire=journalist,
            org=test_org,
            status=PublicationStatus.ACCEPTED,
        )
        journalist_id = journalist.id
        client = make_authenticated_client(app, test_user)

        client.get(url_for("CommandesWipView:cancel", id=commande.id))

        assert _status_of(commande.id) == PublicationStatus.CANCELLED
        bells = db.session.query(Notification).filter_by(receiver_id=journalist_id)
        assert any("annulée" in bell.message for bell in bells)
        assert [mail.status_label for mail in sent_mails] == ["annulée"]

    def test_cancelling_without_destinataire_tells_nobody(
        self,
        app: Flask,
        fresh_db,
        test_user: User,
        test_org: Organisation,
        sent_mails: list[CommandeStatusNotificationMail],
    ) -> None:
        commande = _commande(fresh_db, owner=test_user, destinataire=None, org=test_org)
        client = make_authenticated_client(app, test_user)

        client.get(url_for("CommandesWipView:cancel", id=commande.id))

        assert _status_of(commande.id) == PublicationStatus.CANCELLED
        assert sent_mails == []

    def test_the_page_names_the_destinataire(
        self,
        app: Flask,
        fresh_db,
        test_user: User,
        journalist: User,
        test_org: Organisation,
    ) -> None:
        commande = _commande(
            fresh_db, owner=test_user, destinataire=journalist, org=test_org
        )
        client = make_authenticated_client(app, test_user)

        html = client.get(url_for("CommandesWipView:get", id=commande.id)).get_data(
            as_text=True
        )

        assert "Aïcha Benmahfoud" in html

    def test_the_menu_offers_the_whole_cycle(
        self,
        app: Flask,
        fresh_db,
        test_user: User,
        journalist: User,
        test_org: Organisation,
    ) -> None:
        commande = _commande(
            fresh_db, owner=test_user, destinataire=journalist, org=test_org
        )
        client = make_authenticated_client(app, test_user)

        html = client.get(url_for("CommandesWipView:index")).get_data(as_text=True)

        for action in ("edit", "validate", "cancel", "delete"):
            assert url_for(f"CommandesWipView:{action}", id=commande.id) in html


class TestTheDestinataireOnlyReadsIt:
    """`test_user` is the destinataire; `journalist` placed the commande."""

    def test_the_menu_only_offers_to_read_it(
        self,
        app: Flask,
        fresh_db,
        test_user: User,
        journalist: User,
        test_org: Organisation,
    ) -> None:
        commande = _commande(
            fresh_db, owner=journalist, destinataire=test_user, org=test_org
        )
        client = make_authenticated_client(app, test_user)

        html = client.get(url_for("CommandesWipView:index")).get_data(as_text=True)

        assert url_for("CommandesWipView:get", id=commande.id) in html
        for action in ("edit", "validate", "cancel", "delete"):
            assert url_for(f"CommandesWipView:{action}", id=commande.id) not in html

    @pytest.mark.parametrize("action", ["validate", "cancel"])
    def test_it_cannot_change_its_status(
        self,
        app: Flask,
        fresh_db,
        test_user: User,
        journalist: User,
        test_org: Organisation,
        action: str,
    ) -> None:
        commande = _commande(
            fresh_db, owner=journalist, destinataire=test_user, org=test_org
        )
        client = make_authenticated_client(app, test_user)

        client.get(url_for(f"CommandesWipView:{action}", id=commande.id))

        assert _status_of(commande.id) == PublicationStatus.DRAFT

    def test_it_cannot_edit_it(
        self,
        app: Flask,
        fresh_db,
        test_user: User,
        journalist: User,
        test_org: Organisation,
    ) -> None:
        commande = _commande(
            fresh_db, owner=journalist, destinataire=test_user, org=test_org
        )
        client = make_authenticated_client(app, test_user)

        response = client.get(url_for("CommandesWipView:edit", id=commande.id))

        assert response.status_code in {302, 303}
        assert url_for("CommandesWipView:get", id=commande.id) in response.location

    def test_it_cannot_delete_it(
        self,
        app: Flask,
        fresh_db,
        test_user: User,
        journalist: User,
        test_org: Organisation,
    ) -> None:
        commande = _commande(
            fresh_db, owner=journalist, destinataire=test_user, org=test_org
        )
        client = make_authenticated_client(app, test_user)

        client.get(url_for("CommandesWipView:delete", id=commande.id))

        db.session.remove()
        reloaded = db.session.get(Commande, commande.id)
        assert reloaded is not None
        assert reloaded.deleted_at is None


class TestDirectCreation:
    def test_the_form_asks_for_the_destinataire(
        self, app: Flask, fresh_db, test_user: User
    ) -> None:
        client = make_authenticated_client(app, test_user)

        index = client.get(url_for("CommandesWipView:index")).get_data(as_text=True)
        form = client.get("/wip/commandes/new/").get_data(as_text=True)

        assert "/wip/commandes/new/" in index
        assert "Commande adressée à" in form
        assert 'name="destinataire_id"' in form
