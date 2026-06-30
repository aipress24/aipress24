# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0132 part 3 — route-level coverage for the « Accepter »
action on Sujet (creates a Commande, archives the sujet, notifies the
author)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from app.enums import RoleEnum
from app.flask.extensions import db
from app.flask.routing import url_for
from app.models.auth import KYCProfile, Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models.newsroom.commande import Commande
from app.modules.wip.models.newsroom.sujet import Sujet
from app.services.notifications._models import Notification
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _make_sujet(
    db_session,
    *,
    owner_id: int,
    media_id: int,
    status: PublicationStatus = PublicationStatus.PUBLIC,
) -> Sujet:
    now = datetime.now(UTC)
    sujet = Sujet(
        owner_id=owner_id,
        media_id=media_id,
        commanditaire_id=owner_id,
        titre="Topic title",
        contenu="Topic content",
        status=status,
        date_limite_validite=now + timedelta(days=7),
        date_parution_prevue=now + timedelta(days=14),
    )
    db_session.add(sujet)
    db_session.flush()
    return sujet


@pytest.fixture
def redac_chef(db_session: Session, test_org) -> User:
    """A rédac chef who is a member of the target media's org.

    `profile_code="PM_DIR"` makes them qualify as rédac chef per the
    `#0132 pt 1` gate in `_is_redac_chef_of_org` — required for the
    visibility-aware Sujet routes to admit them on get/edit/accept.
    """
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if role is None:
        role = Role(name=RoleEnum.PRESS_MEDIA.name, description="journalist")
        db_session.add(role)
        db_session.flush()
    user = User(
        email="rc@flounet.example",
        first_name="Annick",
        last_name="Stramazian",
        active=True,
    )
    user.profile = KYCProfile(profile_code="PM_DIR")
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def ordinary_journalist(db_session: Session, test_org) -> User:
    """A regular journalist at the target media's org — same org as
    the rédac chef but NOT qualifying as one (`PM_JR_CP_SAL` profile,
    no BWMi role). Per `#0132 pt 1` they must NOT see or act on
    received Sujets."""
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if role is None:
        role = Role(name=RoleEnum.PRESS_MEDIA.name, description="journalist")
        db_session.add(role)
        db_session.flush()
    user = User(
        email="aicha@flounet.example",
        first_name="Aïcha",
        last_name="BenMahfoud",
        active=True,
    )
    user.profile = KYCProfile(profile_code="PM_JR_CP_SAL")
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def author(db_session: Session) -> User:
    """The journalist author, in a different organisation."""
    author_org = Organisation(name="Fake-Le Quotient du Médecin")
    db_session.add(author_org)
    db_session.flush()
    user = User(
        email="nicolas@example.com",
        first_name="Nicolas",
        last_name="Mouriou",
        active=True,
    )
    user.organisation = author_org
    user.organisation_id = author_org.id
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def author_journalist(db_session: Session) -> User:
    """The journalist author, WITH the PRESS_MEDIA role (so they pass the
    newsroom gate to publish their own sujet) and in their own org."""
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if role is None:
        role = Role(name=RoleEnum.PRESS_MEDIA.name, description="journalist")
        db_session.add(role)
        db_session.flush()
    org = Organisation(name="Fake-Author Press Org")
    db_session.add(org)
    db_session.flush()
    user = User(
        email="claude-author@example.com",
        first_name="Claude",
        last_name="Etchegoyen",
        active=True,
    )
    user.profile = KYCProfile(profile_code="PM_JR_CP_SAL")
    user.organisation = org
    user.organisation_id = org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.flush()
    return user


class TestSujetClochePersistsAcrossTeardown:
    """Bug #0225 (Erick 2026-06-27) — « reçoit le mail mais pas la cloche ».

    Same root cause as #0200 : `NotificationService.post()` only
    `repo.add()`s ; the publish/accept routes commit their state change
    BEFORE calling the notify helper, then redirect with no second commit,
    so the cloche row is rolled back at request teardown. Reproduced by
    simulating teardown (`db.session.remove()`) then asserting COMMITTED
    state. The existing route tests miss it because they patch the notify
    helper entirely.
    """

    def test_proposition_cloche_persists_after_teardown(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        redac_chef: User,
        author_journalist: User,
    ):
        """Publishing a DRAFT sujet to a media must leave the rédac chef a
        COMMITTED bell, not just an email."""
        sujet = _make_sujet(
            db_session,
            owner_id=author_journalist.id,
            media_id=test_org.id,
            status=PublicationStatus.DRAFT,
        )
        db_session.commit()
        redac_chef_id = redac_chef.id

        client = make_authenticated_client(app, author_journalist)
        with patch(
            "app.modules.wip.services.sujet_notifications"
            ".SujetPropositionNotificationMail"
        ):
            resp = client.get(
                url_for("SujetsWipView:publish", id=sujet.id),
                follow_redirects=False,
            )
        assert resp.status_code in (302, 303)

        db.session.remove()  # simulate request teardown
        notifs = (
            db.session.query(Notification).filter_by(receiver_id=redac_chef_id).all()
        )
        assert any("proposé" in n.message for n in notifs), (
            "sujet proposition cloche was rolled back — not committed (#0225)"
        )

    def test_acceptance_cloche_persists_after_teardown(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        redac_chef: User,
        author: User,
    ):
        """Accepting a sujet must leave the author a COMMITTED bell."""
        sujet = _make_sujet(db_session, owner_id=author.id, media_id=test_org.id)
        db_session.commit()
        author_id = author.id

        client = make_authenticated_client(app, redac_chef)
        # cloche fires for real ; only the route's e-mail is patched.
        with patch("app.services.emails.SujetAcceptanceNotificationMail.send"):
            resp = client.get(
                url_for("SujetsWipView:accept", id=sujet.id),
                follow_redirects=False,
            )
        assert resp.status_code in (302, 303)

        db.session.remove()  # simulate request teardown
        notifs = db.session.query(Notification).filter_by(receiver_id=author_id).all()
        assert any("accepté" in n.message for n in notifs), (
            "sujet acceptance cloche was rolled back — not committed (#0225)"
        )


class TestSujetRefuseRoute:
    """Ticket #0225 (Erick 2026-06-27) — « Rajouter, pour le journaliste
    exécutant, le refus du sujet [...] en notification à la cloche ».

    The rédac chef must be able to REFUSE a received sujet (not only
    accept it). Refusing archives the sujet (no Commande) and posts a
    committed bell to the author. Same authorization gate as accept.
    """

    def test_refuse_archives_sujet_and_notifies_author(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        redac_chef: User,
        author: User,
    ):
        sujet = _make_sujet(db_session, owner_id=author.id, media_id=test_org.id)
        db_session.commit()
        sujet_id = sujet.id
        author_id = author.id

        client = make_authenticated_client(app, redac_chef)
        resp = client.get(
            url_for("SujetsWipView:refuse", id=sujet.id),
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

        db.session.remove()  # simulate teardown — the cloche must be COMMITTED
        sujet_after = db.session.get(Sujet, sujet_id)
        assert sujet_after.status == PublicationStatus.ARCHIVED
        # Refusal must NOT create a Commande.
        assert db.session.query(Commande).filter_by(titre="Topic title").all() == []
        notifs = db.session.query(Notification).filter_by(receiver_id=author_id).all()
        assert any("refusé" in n.message for n in notifs), (
            "author must get a committed « refusé » cloche (#0225)"
        )

    def test_refuse_denies_non_redac_chef(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        ordinary_journalist: User,
        author: User,
    ):
        """An ordinary journalist at the target media (not a rédac chef)
        must not be able to refuse — same VULN-001 guard as accept."""
        sujet = _make_sujet(db_session, owner_id=author.id, media_id=test_org.id)
        db_session.commit()
        sujet_id = sujet.id

        client = make_authenticated_client(app, ordinary_journalist)
        resp = client.get(
            url_for("SujetsWipView:refuse", id=sujet.id),
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303, 403, 404)

        db.session.remove()
        assert db.session.get(Sujet, sujet_id).status == PublicationStatus.PUBLIC


class TestSujetAcceptRoute:
    def test_accept_creates_commande_archives_sujet_redirects_to_commandes(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        redac_chef: User,
        author: User,
    ):
        sujet = _make_sujet(db_session, owner_id=author.id, media_id=test_org.id)
        db_session.commit()
        sujet_id = sujet.id

        client = make_authenticated_client(app, redac_chef)
        with patch(
            "app.modules.wip.crud.cbvs.sujets.notify_author_of_sujet_acceptance"
        ):
            response = client.get(
                url_for("SujetsWipView:accept", id=sujet.id),
                follow_redirects=False,
            )

        assert response.status_code in (302, 303)
        assert "/wip/commandes" in response.headers.get("Location", "")

        db_session.expire_all()
        # Sujet archived
        sujet_after = db_session.get(Sujet, sujet_id)
        assert sujet_after.status == PublicationStatus.ARCHIVED
        # A new Commande exists with the sujet's title.
        commandes = (
            db_session.query(Commande)
            .filter_by(titre="Topic title", media_id=test_org.id)
            .all()
        )
        assert len(commandes) == 1
        # Bug #0225 — owner is the journalist author (so it shows in their
        # newsroom); the rédac chef is the commanditaire.
        assert commandes[0].owner_id == author.id
        assert commandes[0].commanditaire_id == redac_chef.id

    def test_accept_route_refuses_non_redac_chef(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        author: User,
    ):
        """A user from another org can't accept the sujet. The route
        either redirects with a flash error (when the user has
        newsroom access but not on the right media) or returns 403
        from the upstream `before_request` guard (when the user is
        in an org that has no newsroom access at all). Either way the
        sujet must NOT transition to ARCHIVED."""
        sujet = _make_sujet(db_session, owner_id=author.id, media_id=test_org.id)
        db_session.commit()
        sujet_id = sujet.id

        client = make_authenticated_client(app, author)
        response = client.get(
            url_for("SujetsWipView:accept", id=sujet.id),
            follow_redirects=False,
        )

        # Route either denies upstream (403) or downstream (302 with
        # flash error). What matters : the sujet state stays PUBLIC.
        assert response.status_code in (302, 303, 403)

        db_session.expire_all()
        sujet_after = db_session.get(Sujet, sujet_id)
        assert sujet_after.status == PublicationStatus.PUBLIC, (
            "unauthorized user must not archive the sujet (#0132/3)"
        )


class TestSujetPublisherTextOnEdit:
    """Bug #0132 point 3 (Erick, 2026-06-02) :

    > Si Annick Stramazian va dans le menu "Modifier", apparaît la
    > mention "Publié pour le compte de Fake-Les Editions numérique
    > du 0 et du 1" qui sort de nulle part puisque Nicolas Mouriou
    > travaille chez "Fake-Le Quotient du Médecin".

    Verifies that the #0135 fix (FormRenderer reads `model.publisher`
    instead of `g.user.organisation`) also covers the Sujet flow.
    The Sujet's `publisher_id` is populated to the author's org by
    `SujetsWipView._post_update_model` on save ; subsequent renders
    must reflect *that* org, regardless of who opens the form.
    """

    def test_redac_chef_editing_a_sujet_sees_author_org_in_header(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        redac_chef: User,
        author: User,
    ):
        # Sujet « proposed by Nicolas to test_org » — publisher_id
        # pinned to Nicolas's org as the application would do via
        # `_post_update_model` on save.
        sujet = _make_sujet(db_session, owner_id=author.id, media_id=test_org.id)
        sujet.publisher_id = author.organisation_id
        db_session.commit()

        client = make_authenticated_client(app, redac_chef)
        response = client.get(
            url_for("SujetsWipView:edit", id=sujet.id),
            follow_redirects=False,
        )
        assert response.status_code == 200
        body = response.data.decode()

        author_org_name = "Fake-Le Quotient du Médecin"
        redac_chef_org_name = test_org.name  # "WIP Test Organization"

        # Quotes get HTML-escaped to `&#34;` in the rendered form
        # template — assert on the unquoted name to stay readable.
        assert "Publié pour le compte de" in body
        assert author_org_name in body, (
            "the header must follow the sujet's publisher (Nicolas's "
            "org), not the editing user's org (#0132 point 3 / #0135)"
        )
        assert (
            f"Publié pour le compte de &#34;{redac_chef_org_name}&#34;" not in body
            and f'Publié pour le compte de "{redac_chef_org_name}"' not in body
        ), (
            "the rédac chef's own org must NOT leak into the "
            "'Publié pour le compte de' header (#0132 point 3)"
        )


class TestSujetAuthorMiniCardOnDetail:
    """Bug #0132 point 2 (Erick, 2026-06-02) :

    > 2- On identifie toujours très mal l'auteur. Certes, dans
    > NEWSROOM/Sujets chez Annick Stramazian, en cliquant sur "Voir",
    > il y a un encadré en bleu pâle avec la mention "Nicolas
    > Mouriou, Journaliste avec carte de presse en micro-entreprise,
    > Fake-Le quotient du Médecin". Mais on ne voit toujours pas la
    > carte résumée du journaliste avec sa photo.

    The pale-blue text-only box is replaced by the shared
    `poster_card` mini-card (photo + name + role + organisation +
    profile link + BW link if available).
    """

    @pytest.fixture
    def author_with_role(self, db_session: Session) -> User:
        role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
        if role is None:
            role = Role(name=RoleEnum.PRESS_MEDIA.name, description="journalist")
            db_session.add(role)
            db_session.flush()
        author_org = Organisation(name="Fake-Le Quotient du Médecin")
        db_session.add(author_org)
        db_session.flush()
        user = User(
            email="nicolas-pt2@example.com",
            first_name="Nicolas",
            last_name="Mouriou",
            active=True,
        )
        user.profile = KYCProfile()
        user.photo = b""
        user.organisation = author_org
        user.organisation_id = author_org.id
        user.roles.append(role)
        db_session.add(user)
        db_session.flush()
        return user

    def test_sujet_get_renders_author_mini_card(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        redac_chef: User,
        author_with_role: User,
    ):
        sujet = _make_sujet(
            db_session, owner_id=author_with_role.id, media_id=test_org.id
        )
        sujet.publisher_id = author_with_role.organisation_id
        db_session.commit()

        client = make_authenticated_client(app, redac_chef)
        response = client.get(
            url_for("SujetsWipView:get", id=sujet.id),
            follow_redirects=False,
        )
        assert response.status_code == 200
        body = response.data.decode()

        assert "Nicolas Mouriou" in body, "author name must appear"
        assert f"/swork/members/{author_with_role.id}" in body, (
            "author mini-card must link to the profile page (#0132 pt 2)"
        )
        # The mini-card is implemented via the shared `poster_card`
        # macro — assert the macro's visual marker is present (the
        # « Voir le profil » CTA from the macro).
        assert "Voir le profil" in body, (
            "the rich poster_card macro must replace the legacy "
            "text-only blue box (#0132 pt 2)"
        )


class TestSujetRedacChefGate:
    """Security review VULN-001 — the `#0132 pt 1` visibility gate
    must apply to the detail / edit / accept routes too, not only the
    LIST datasource. A regular journalist at the target media (same
    org as the rédac chef but not qualifying as one) must NOT be able
    to view or act on received Sujets via direct URL.
    """

    def test_get_route_denies_ordinary_journalist_at_target_media(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        ordinary_journalist: User,
        author: User,
    ):
        """Aïcha (regular journalist at Fake-01Flounet) cannot view a
        Sujet sent to her org's rédac chef by direct URL."""
        sujet = _make_sujet(db_session, owner_id=author.id, media_id=test_org.id)
        db_session.commit()

        client = make_authenticated_client(app, ordinary_journalist)
        response = client.get(
            url_for("SujetsWipView:get", id=sujet.id),
            follow_redirects=False,
        )

        assert response.status_code == 404, (
            "an ordinary journalist must not see Sujets received by "
            "their media's rédac chef via direct URL (VULN-001)"
        )

    def test_edit_route_denies_ordinary_journalist_at_target_media(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        ordinary_journalist: User,
        author: User,
    ):
        """Aïcha cannot open the edit form for the rédac chef's
        received Sujet either."""
        sujet = _make_sujet(db_session, owner_id=author.id, media_id=test_org.id)
        db_session.commit()

        client = make_authenticated_client(app, ordinary_journalist)
        response = client.get(
            url_for("SujetsWipView:edit", id=sujet.id),
            follow_redirects=False,
        )

        assert response.status_code == 404

    def test_accept_route_denies_ordinary_journalist_at_target_media(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        ordinary_journalist: User,
        author: User,
    ):
        """Aïcha (same org as the rédac chef but not a rédac chef
        herself) must NOT be able to accept a Sujet by direct URL —
        the previous code only checked `accepter.organisation_id ==
        sujet.media_id`, which she trivially passes."""
        sujet = _make_sujet(db_session, owner_id=author.id, media_id=test_org.id)
        db_session.commit()
        sujet_id = sujet.id

        client = make_authenticated_client(app, ordinary_journalist)
        with patch(
            "app.modules.wip.crud.cbvs.sujets.notify_author_of_sujet_acceptance"
        ):
            response = client.get(
                url_for("SujetsWipView:accept", id=sujet.id),
                follow_redirects=False,
            )

        assert response.status_code in (302, 303, 403, 404)

        db_session.expire_all()
        sujet_after = db_session.get(Sujet, sujet_id)
        assert sujet_after.status == PublicationStatus.PUBLIC, (
            "a non-rédac-chef journalist must not archive the rédac "
            "chef's received Sujet (VULN-001)"
        )
        # No Commande must have been materialised.
        commandes = db_session.query(Commande).filter_by(media_id=test_org.id).all()
        assert commandes == [], (
            "no Commande must be created when a non-rédac-chef accepts "
            "a Sujet (VULN-001)"
        )

    def test_get_route_denies_user_at_unrelated_org(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        author: User,
    ):
        """A third party with newsroom access but at a completely
        unrelated org must not be able to read a Sujet by guessing its
        (sequential BigInteger) id. Cross-org information disclosure.
        """
        sujet = _make_sujet(db_session, owner_id=author.id, media_id=test_org.id)
        db_session.commit()

        # Build a third journalist : neither the sujet owner, nor a
        # member of the target media's org, but holding PRESS_MEDIA
        # so they pass the upstream `before_request` newsroom gate.
        role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
        if role is None:
            role = Role(name=RoleEnum.PRESS_MEDIA.name, description="journalist")
            db_session.add(role)
            db_session.flush()
        third_org = Organisation(name="Fake-Unrelated Media")
        db_session.add(third_org)
        db_session.flush()
        third_journalist = User(
            email="probe@example.com",
            first_name="Probe",
            last_name="Journalist",
            active=True,
        )
        third_journalist.profile = KYCProfile(profile_code="PM_JR_CP_SAL")
        third_journalist.organisation = third_org
        third_journalist.organisation_id = third_org.id
        third_journalist.roles.append(role)
        db_session.add(third_journalist)
        db_session.commit()

        client = make_authenticated_client(app, third_journalist)
        response = client.get(
            url_for("SujetsWipView:get", id=sujet.id),
            follow_redirects=False,
        )

        # Direct URL access to a Sujet they neither own nor receive
        # must 404 (existence-hiding).
        assert response.status_code == 404


class TestSujetAcceptSendsMailToAuthor:
    """Bug #0132 point 6 (Erick, 2026-06-02) :

    > Nicolas Mouriou n'en est pas averti. Il faudrait donc que
    > Nicolas Mouriou ait une notification d'alerte ET que la
    > commande apparaisse dans son espace WORK/NEWSROOM/Commande
    > avec la mention "Commanditaire" et la mini-carte d'Annick
    > Stramazian, rédactrice en chef de Fake-01 Flounet.

    The bell notification is already wired in via
    `notify_author_of_sujet_acceptance`. This test pins the email
    side : when the rédac chef clicks « Accepter », a
    `SujetAcceptanceNotificationMail` is sent to the original
    journalist with the « Commanditaire » mention.
    """

    def test_accept_sends_acceptance_mail_to_author(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        redac_chef: User,
        author: User,
    ):
        sujet = _make_sujet(db_session, owner_id=author.id, media_id=test_org.id)
        db_session.commit()

        sent: list[object] = []

        def fake_send(self):
            sent.append(self)

        client = make_authenticated_client(app, redac_chef)
        with (
            patch("app.modules.wip.crud.cbvs.sujets.notify_author_of_sujet_acceptance"),
            patch(
                "app.services.emails.SujetAcceptanceNotificationMail.send",
                fake_send,
            ),
        ):
            response = client.get(
                url_for("SujetsWipView:accept", id=sujet.id),
                follow_redirects=False,
            )

        assert response.status_code in (302, 303)
        assert len(sent) == 1, "exactly one acceptance mail must be sent"
        mail = sent[0]
        assert mail.recipient == author.email
        assert mail.accepter_full_name == redac_chef.full_name
        assert mail.accepter_organisation == test_org.name
        assert mail.sujet_title == "Topic title"
        assert "/wip/commandes" in mail.commande_url
