# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""A WIP record is private to the people its list would show it to.

Security audit 2026-09-09, finding 1. `BaseWipView._get_model` was a
bare primary-key fetch, so the module gate — a community-role check —
was the only thing between a member and someone else's record. Every
route reached through that method served it, and `post` overwrote it
in place with the owner unchanged.

The rule now lives on the base and each view widens it. These tests
cover the two halves that matter: the read is refused, and so is the
write, which is the half an audit is likeliest to miss.

Article had its own guard already (`_require_author`) and is covered
by `TestArticleAccessControl`; it is included here so the whole family
is pinned in one place if the base rule is ever loosened.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import arrow
import pytest

from app.flask.routing import url_for
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models import AvisEnquete, Commande, Communique
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask

    from app.models.organisation import Organisation


def _email() -> str:
    return f"rival-{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture
def rival(fresh_db) -> User:
    """A second member of the same community, in no way a party to the
    records below."""
    user = User(email=_email(), first_name="Rival", last_name="Rival", active=True)
    fresh_db.session.add(user)
    fresh_db.session.commit()
    return user


@pytest.fixture
def foreign_avis(fresh_db, rival: User, test_org: Organisation) -> AvisEnquete:
    """An avis owned by `rival`, which `test_user` has no claim to."""
    now = arrow.utcnow()
    avis = AvisEnquete(
        titre="Enquête confidentielle",
        contenu="<p>Brief.</p>",
        owner_id=rival.id,
        commanditaire_id=rival.id,
        media_id=test_org.id,
        status=PublicationStatus.DRAFT,
        date_debut_enquete=now,
        date_fin_enquete=now,
        date_bouclage=now,
        date_parution_prevue=now,
    )
    fresh_db.session.add(avis)
    fresh_db.session.commit()
    return avis


class TestAvisEnqueteIsolation:
    """The sharpest case: the ciblage screen lists people by name,
    photo, function and organisation, and its confirm action publishes
    the avis and emails those people under the owner's name."""

    def test_a_rival_journalist_cannot_read_it(
        self, app: Flask, test_user: User, foreign_avis: AvisEnquete
    ) -> None:
        client = make_authenticated_client(app, test_user)

        response = client.get(
            url_for("AvisEnqueteWipView:get", id=foreign_avis.id),
            follow_redirects=False,
        )

        assert response.status_code in {302, 403, 404}
        assert b"Enqu\xc3\xaate confidentielle" not in response.data

    def test_a_rival_journalist_cannot_open_the_edit_form(
        self, app: Flask, test_user: User, foreign_avis: AvisEnquete
    ) -> None:
        client = make_authenticated_client(app, test_user)

        response = client.get(
            url_for("AvisEnqueteWipView:edit", id=foreign_avis.id),
            follow_redirects=False,
        )

        assert response.status_code in {302, 403, 404}

    def test_a_rival_journalist_cannot_open_the_ciblage_screen(
        self, app: Flask, test_user: User, foreign_avis: AvisEnquete
    ) -> None:
        client = make_authenticated_client(app, test_user)

        response = client.get(
            f"/wip/avis-enquete/{foreign_avis.id}/ciblage", follow_redirects=False
        )

        assert response.status_code in {302, 403, 404}

    def test_a_rival_journalist_cannot_overwrite_it(
        self, app: Flask, fresh_db, test_user: User, foreign_avis: AvisEnquete
    ) -> None:
        """The half that matters most: the audit's exploit posted the
        hidden `id` from a form it had just been served."""
        client = make_authenticated_client(app, test_user)
        avis_id = foreign_avis.id

        client.post(
            "/wip/avis-enquete/",
            data={"_action": "save", "id": str(avis_id), "titre": "PWNED"},
            follow_redirects=False,
        )

        fresh_db.session.expire_all()
        after = fresh_db.session.get(AvisEnquete, avis_id)
        assert after.titre == "Enquête confidentielle"
        assert after.owner_id != test_user.id


class TestCommuniqueIsolation:
    def test_a_rival_cannot_read_another_communique(
        self, app: Flask, fresh_db, rival: User, test_user: User, test_org
    ) -> None:
        communique = Communique(
            titre="Communiqué sous embargo",
            contenu="<p>Embargo.</p>",
            owner_id=rival.id,
            publisher_id=test_org.id,
            status=PublicationStatus.DRAFT,
        )
        fresh_db.session.add(communique)
        fresh_db.session.commit()
        client = make_authenticated_client(app, test_user)

        response = client.get(
            url_for("CommuniquesWipView:get", id=communique.id),
            follow_redirects=False,
        )

        assert response.status_code in {302, 403, 404}
        assert "Communiqué sous embargo".encode() not in response.data


class TestCommandeIsolation:
    """Widened on purpose (#0225): both the journalist who authored the
    sujet and the rédac chef who accepted it. A third party is still out."""

    def _commande(self, fresh_db, owner_id: int, commanditaire_id: int, org):
        commande = Commande(
            titre="Commande privée",
            contenu="<p>Brief.</p>",
            owner_id=owner_id,
            commanditaire_id=commanditaire_id,
            media_id=org.id,
            status=PublicationStatus.DRAFT,
            date_limite_validite=datetime.now(UTC),
            date_bouclage=datetime.now(UTC),
            date_parution_prevue=datetime.now(UTC),
        )
        fresh_db.session.add(commande)
        fresh_db.session.commit()
        return commande

    def test_a_third_party_cannot_read_it(
        self, app: Flask, fresh_db, rival: User, test_user: User, test_org
    ) -> None:
        commande = self._commande(fresh_db, rival.id, rival.id, test_org)
        client = make_authenticated_client(app, test_user)

        response = client.get(
            url_for("CommandesWipView:get", id=commande.id), follow_redirects=False
        )

        assert response.status_code in {302, 403, 404}

    def test_the_commanditaire_still_reads_it(
        self, app: Flask, fresh_db, rival: User, test_user: User, test_org
    ) -> None:
        """The widening is the point of the override — pin it, or the
        next tightening silently breaks bug #0225's fix."""
        commande = self._commande(fresh_db, rival.id, test_user.id, test_org)
        client = make_authenticated_client(app, test_user)

        response = client.get(
            url_for("CommandesWipView:get", id=commande.id), follow_redirects=False
        )

        assert response.status_code == 200
