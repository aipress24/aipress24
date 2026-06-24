# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Bug 0132: tests for sujet publication workflow.

Before this fix `SujetsWipView` had no publish action, so journalists' sujet
proposals stayed in DRAFT forever and the targeted media never received
anything. This module covers:

- Sujet.publish() / unpublish() lifecycle on the model.
- SujetsTable.get_actions() exposes "Publier" / "Dépublier" depending on status.
- notify_media_of_sujet_proposition() routes the email to the media's BW owner.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from flask import g
from svcs.flask import container

from app.models.auth import KYCProfile, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.crud.cbvs._forms import SujetForm
from app.modules.wip.crud.cbvs.commandes import CommandeDataSource
from app.modules.wip.crud.cbvs.sujets import (
    _SUJET_VIEW_TEMPLATE,
    SujetsTable,
    SujetsWipView,
)
from app.modules.wip.models.newsroom.commande import Commande
from app.modules.wip.models.newsroom.sujet import Sujet
from app.modules.wip.services.newsroom.sujet_accept import accept_sujet_as_commande
from app.modules.wip.services.sujet_notifications import (
    notify_media_of_sujet_proposition,
)
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, scoped_session


@pytest.fixture
def media_org(db_session: Session) -> Organisation:
    org = Organisation(name="Fake-01 Flounet")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def author_user(db_session: Session) -> User:
    user = User(email="nicolas@example.com", first_name="Nicolas", last_name="Moriou")
    db_session.add(user)
    db_session.flush()
    return user


def _make_sujet(
    db_session: Session,
    *,
    media_id: int,
    owner_id: int,
    titre: str = "Mon enquête",
    contenu: str = "Brief de l'enquête",
    status: PublicationStatus = PublicationStatus.DRAFT,
) -> Sujet:
    sujet = Sujet(
        titre=titre,
        contenu=contenu,
        date_limite_validite=dt.datetime(2026, 12, 31, tzinfo=dt.UTC),
        date_parution_prevue=dt.datetime(2027, 1, 31, tzinfo=dt.UTC),
        media_id=media_id,
        owner_id=owner_id,
        commanditaire_id=owner_id,
    )
    sujet.status = status  # type: ignore[assignment]
    db_session.add(sujet)
    db_session.flush()
    return sujet


class TestSujetPublishLifecycle:
    def test_can_publish_in_draft_status(
        self, db_session: Session, media_org: Organisation, author_user: User
    ):
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author_user.id)
        assert sujet.can_publish() is True

    def test_publish_moves_to_public(
        self, db_session: Session, media_org: Organisation, author_user: User
    ):
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author_user.id)
        sujet.publish()
        assert sujet.status == PublicationStatus.PUBLIC

    def test_publish_idempotency_raises(
        self, db_session: Session, media_org: Organisation, author_user: User
    ):
        sujet = _make_sujet(
            db_session,
            media_id=media_org.id,
            owner_id=author_user.id,
            status=PublicationStatus.PUBLIC,
        )
        with pytest.raises(ValueError, match="DRAFT"):
            sujet.publish()

    def test_publish_requires_title(
        self, db_session: Session, media_org: Organisation, author_user: User
    ):
        sujet = _make_sujet(
            db_session, media_id=media_org.id, owner_id=author_user.id, titre=""
        )
        with pytest.raises(ValueError, match="titre"):
            sujet.publish()

    def test_publish_requires_content(
        self, db_session: Session, media_org: Organisation, author_user: User
    ):
        sujet = _make_sujet(
            db_session, media_id=media_org.id, owner_id=author_user.id, contenu=""
        )
        with pytest.raises(ValueError, match="contenu"):
            sujet.publish()

    def test_unpublish_returns_to_draft(
        self, db_session: Session, media_org: Organisation, author_user: User
    ):
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author_user.id)
        sujet.publish()

        sujet.unpublish()

        assert sujet.status == PublicationStatus.DRAFT

    def test_unpublish_only_from_public(
        self, db_session: Session, media_org: Organisation, author_user: User
    ):
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author_user.id)
        with pytest.raises(ValueError, match="PUBLIC"):
            sujet.unpublish()


class TestSujetAcceptAction:
    """Ticket #0132 part 3 (Erick, 2026-05-22) : « il manque la fonction
    "Accepter" qui fait passer le sujet à NEWSROOM/Commandes avec
    notification à l'Auteur ». The rédac chef of a target media must
    be able to accept a PUBLIC sujet, which (1) creates a Commande
    copying the sujet's content + (2) transitions the sujet to
    ARCHIVED + (3) notifies the author.
    """

    def test_accept_creates_commande_and_archives_sujet(
        self,
        db_session: scoped_session,
        media_org: Organisation,
        author_user: User,
    ):
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author_user.id)
        sujet.titre = "Topic title"
        sujet.contenu = "Topic content"
        sujet.publish()  # → PUBLIC
        db_session.flush()

        redac_chef = User(email="redacchef@flounet.example", active=True)
        # Security VULN-001 : `accept_sujet_as_commande` now also
        # requires rédac chef qualification — not just org membership.
        redac_chef.profile = KYCProfile(profile_code="PM_DIR")
        redac_chef.organisation = media_org
        redac_chef.organisation_id = media_org.id
        db_session.add(redac_chef)
        db_session.flush()

        commande = accept_sujet_as_commande(sujet, redac_chef)

        # (1) Commande was created with sujet content.
        assert isinstance(commande, Commande)
        assert commande.titre == "Topic title"
        assert commande.contenu == "Topic content"
        # Bug #0225 — owner is the journalist (sujet author) so it shows
        # in their newsroom; the rédac chef is the commanditaire.
        assert commande.owner_id == author_user.id
        assert commande.commanditaire_id == redac_chef.id
        assert commande.media_id == media_org.id
        # (2) Sujet transitioned to ARCHIVED (no longer in « new » list).
        assert sujet.status == PublicationStatus.ARCHIVED

    def test_accept_refuses_if_not_redac_chef_of_target_media(
        self,
        db_session: scoped_session,
        media_org: Organisation,
        author_user: User,
    ):
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author_user.id)
        sujet.publish()
        db_session.flush()

        outsider = User(email="outsider@elsewhere.example", active=True)
        outsider_org = Organisation(name="Outsider Org")
        db_session.add(outsider_org)
        db_session.flush()
        outsider.organisation = outsider_org
        outsider.organisation_id = outsider_org.id
        db_session.add(outsider)
        db_session.flush()

        with pytest.raises(ValueError, match="not authorized"):
            accept_sujet_as_commande(sujet, outsider)

    def test_accept_refuses_if_sujet_not_public(
        self,
        db_session: scoped_session,
        media_org: Organisation,
        author_user: User,
    ):
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author_user.id)
        # Stays DRAFT — not acceptable as a commande.
        redac_chef = User(email="rc2@flounet.example", active=True)
        redac_chef.profile = KYCProfile(profile_code="PM_DIR")
        redac_chef.organisation = media_org
        redac_chef.organisation_id = media_org.id
        db_session.add(redac_chef)
        db_session.flush()

        with pytest.raises(ValueError, match="not PUBLIC|not in PUBLIC"):
            accept_sujet_as_commande(sujet, redac_chef)


class TestCommandeVisibility:
    """Bug #0225 — once a sujet is accepted, the resulting Commande must
    show in BOTH the journalist's (owner) and the rédac chef's
    (commanditaire) NEWSROOM/Commandes list — not just the rédac chef's."""

    @staticmethod
    def _titles_and_count(app, model_cls, user):
        with app.test_request_context():
            g.user = user
            ds = CommandeDataSource(model_class=model_cls, q="")
            return [c.titre for c in ds.get_items()], ds.get_count()

    def test_commande_visible_to_both_author_and_redac_chef(
        self, app, db_session: scoped_session, media_org: Organisation, author_user: User
    ):
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author_user.id)
        sujet.titre = "Commande 0225"
        sujet.publish()
        db_session.flush()

        redac_chef = User(email="rc0225@flounet.example", active=True)
        redac_chef.profile = KYCProfile(profile_code="PM_DIR")
        redac_chef.organisation = media_org
        redac_chef.organisation_id = media_org.id
        db_session.add(redac_chef)
        db_session.flush()

        accept_sujet_as_commande(sujet, redac_chef)
        db_session.flush()

        # Journalist (owner) sees it.
        author_titles, author_count = self._titles_and_count(
            app, Commande, author_user
        )
        assert "Commande 0225" in author_titles
        assert author_count >= 1

        # Rédac chef (commanditaire) sees it too.
        rc_titles, rc_count = self._titles_and_count(app, Commande, redac_chef)
        assert "Commande 0225" in rc_titles
        assert rc_count >= 1

        # An unrelated user sees nothing.
        other = User(email="other0225@flounet.example", active=True)
        db_session.add(other)
        db_session.flush()
        other_titles, _ = self._titles_and_count(app, Commande, other)
        assert "Commande 0225" not in other_titles


class TestSujetsTableActions:
    def test_draft_item_shows_publier(self):
        table = SujetsTable()
        item = MagicMock(id=1, status=PublicationStatus.DRAFT)

        labels = [a["label"] for a in table.get_actions(item)]

        assert "Publier" in labels
        assert "Dépublier" not in labels

    def test_public_item_shows_depublier(self):
        table = SujetsTable()
        item = MagicMock(id=1, status=PublicationStatus.PUBLIC)

        labels = [a["label"] for a in table.get_actions(item)]

        assert "Dépublier" in labels
        assert "Publier" not in labels

    def test_core_actions_always_present(self):
        table = SujetsTable()
        item = MagicMock(id=1, status=PublicationStatus.DRAFT)

        labels = [a["label"] for a in table.get_actions(item)]

        assert "Voir" in labels
        assert "Modifier" in labels
        assert "Supprimer" in labels


class TestSujetFormFields:
    """Bug #0132 final cleanup: media_id label must be unambiguous and
    the developed view must display the author so the chief editor of
    the receiving media knows who proposed the topic."""

    def test_media_id_label_says_destinataire(self):
        form = SujetForm()
        assert "destinataire" in form.media_id.label.text.lower()

    def test_extra_view_html_shows_author_in_edit_mode(
        self, db_session: Session, media_org: Organisation, author_user: User
    ):
        """The chief editor opens the developed sujet (edit mode) and must
        see the author — they were already shown in pure view mode."""
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author_user.id)
        view = SujetsWipView()
        html = view._extra_view_html(sujet, mode="edit")
        assert "Auteur" in html
        assert author_user.full_name in html

    def test_extra_view_html_escapes_author_name(
        self, db_session: Session, media_org: Organisation
    ):
        """The output is rendered with `|safe`, so any HTML in the author's
        name must be escaped to avoid XSS."""
        author = User(email="xss@example.com", first_name="<script>", last_name="x")
        db_session.add(author)
        db_session.flush()
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author.id)
        view = SujetsWipView()
        html = view._extra_view_html(sujet, mode="edit")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_extra_view_html_renders_profile_link_to_swork_member(
        self,
        db_session: Session,
        media_org: Organisation,
        author_user: User,
    ):
        """Bug #0132 part 2 (Erick, 2026-06-02) : the author block was
        upgraded from a text-only blue box to the shared `poster_card`
        macro. The mini-card must include a clickable link to the
        author's profile page in /swork/members/<id> so the rédac chef
        can vérifier à qui ils ont affaire."""
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author_user.id)
        view = SujetsWipView()
        html = view._extra_view_html(sujet, mode="view")
        assert f"/swork/members/{author_user.id}" in html, (
            "author mini-card must link to the profile page (#0132/2)"
        )

    def test_extra_view_html_includes_author_name_and_organisation(
        self, db_session: Session, media_org: Organisation
    ):
        """The author mini-card must surface the author's name and
        organisation (the rédac chef needs both to identify the
        proposer). The fonction line — computed from KYC fields like
        `fonctions_journalisme` or `metiers` — is rendered when
        available, but not required to be present (#0132 / Erick
        2026-06-02)."""
        org = Organisation(name="Fake-Le Quotient du Médecin")
        db_session.add(org)
        db_session.flush()
        author = User(
            email="nico@example.com", first_name="Nicolas", last_name="Mouriou"
        )
        author.profile = KYCProfile(
            match_making={
                "fonctions_journalisme": [
                    "journaliste avec carte de presse en micro-entreprise",
                ]
            }
        )
        author.organisation = org
        author.organisation_id = org.id
        db_session.add(author)
        db_session.flush()
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author.id)

        html = SujetsWipView()._extra_view_html(sujet, mode="view")

        assert "Nicolas Mouriou" in html
        assert "Fake-Le Quotient du Médecin" in html
        # The fonction sourced from `fonctions_journalisme` appears in
        # the metier_fonction line of the poster_card macro.
        assert "journaliste avec carte de presse en micro-entreprise" in html

    def test_sujet_view_template_renders_author_before_form(self):
        """Bug #0132 (2026-05-14): the author block sits *above* the
        form. Sujet uses its own view template (the shared one keeps
        `extra_view_html` below the form for Communiqué's carousel,
        bug #0128)."""
        assert _SUJET_VIEW_TEMPLATE.index(
            "extra_view_html"
        ) < _SUJET_VIEW_TEMPLATE.index("form_rendered")


class TestNotifyMediaOfSujetProposition:
    def test_skips_when_author_belongs_to_target_media(self, monkeypatch):
        sent = []

        def fake_send(self):
            sent.append(self)

        monkeypatch.setattr(
            "app.modules.wip.services.sujet_notifications."
            "SujetPropositionNotificationMail.send",
            fake_send,
            raising=True,
        )
        author = SimpleNamespace(organisation_id=42, email="j@x", full_name="Jane Doe")
        media_org = SimpleNamespace(id=42, bw_name="Same media", name="X")

        notify_media_of_sujet_proposition(
            author=author,
            media_org=media_org,
            sujet_title="Hello",
            sujet_url="https://x/sujet/1",
        )

        assert sent == []

    def test_skips_when_no_recipient_resolved(self, monkeypatch):
        sent = []

        def fake_send(self):
            sent.append(self)

        monkeypatch.setattr(
            "app.modules.wip.services.sujet_notifications."
            "SujetPropositionNotificationMail.send",
            fake_send,
            raising=True,
        )
        # _pick_bw_owner_user returns None because no BW + no members.
        monkeypatch.setattr(
            "app.modules.wip.services.sujet_notifications._pick_bw_owner_user",
            lambda media_org: None,
        )
        author = SimpleNamespace(organisation_id=1, email="j@x", full_name="Jane")
        media_org = SimpleNamespace(id=99, bw_name="Empty media", name="X")

        notify_media_of_sujet_proposition(
            author=author,
            media_org=media_org,
            sujet_title="Hello",
            sujet_url="https://x/sujet/1",
        )

        assert sent == []

    def test_sends_when_bw_owner_resolved(self, monkeypatch):
        sent = []

        def fake_send(self):
            sent.append(self)

        monkeypatch.setattr(
            "app.modules.wip.services.sujet_notifications."
            "SujetPropositionNotificationMail.send",
            fake_send,
            raising=True,
        )
        recipient = SimpleNamespace(
            id=42, email="rc@flounet.example", full_name="RC Flounet"
        )
        monkeypatch.setattr(
            "app.modules.wip.services.sujet_notifications._pick_bw_owner_user",
            lambda media_org: recipient,
        )
        author = SimpleNamespace(
            organisation_id=1, email="nicolas@example", full_name="Nicolas Moriou"
        )
        media_org = SimpleNamespace(id=99, bw_name="Fake-01 Flounet", name="01F")

        notify_media_of_sujet_proposition(
            author=author,
            media_org=media_org,
            sujet_title="L'IA dans la supply chain",
            sujet_url="https://aipress24.com/wip/sujets/12",
        )

        assert len(sent) == 1
        mail = sent[0]
        assert mail.recipient == "rc@flounet.example"
        assert mail.media_name == "Fake-01 Flounet"
        assert mail.sujet_title == "L'IA dans la supply chain"
        assert mail.sender_full_name == "Nicolas Moriou"

    def test_posts_in_app_notification_to_bw_owner(self, monkeypatch):
        """Ticket #0132 part 5 (Erick, 2026-05-22) : « Les propositions
        de sujets devraient faire l'objet d'une notification à la
        cloche ». In addition to the email, post an in-app notif so
        the rédac chef sees the signal inside the platform too."""
        # Don't let the email side-effect bleed (templates would fail).
        monkeypatch.setattr(
            "app.modules.wip.services.sujet_notifications."
            "SujetPropositionNotificationMail.send",
            lambda self: None,
            raising=True,
        )
        recipient = SimpleNamespace(
            id=7, email="rc@x", full_name="RC", is_anonymous=False, active=True
        )
        monkeypatch.setattr(
            "app.modules.wip.services.sujet_notifications._pick_bw_owner_user",
            lambda media_org: recipient,
        )

        posted: list[tuple] = []

        def fake_post(user, message, url=""):
            posted.append((user, message, url))

        # Replace the NotificationService instance method.
        notif_service = container.get(NotificationService)
        monkeypatch.setattr(notif_service, "post", fake_post)

        author = SimpleNamespace(
            organisation_id=1, email="nicolas@x", full_name="Nicolas Mouriou"
        )
        media_org = SimpleNamespace(id=99, bw_name="Fake-01 Flounet", name="01F")

        notify_media_of_sujet_proposition(
            author=author,
            media_org=media_org,
            sujet_title="L'IA dans la supply chain",
            sujet_url="https://aipress24.com/wip/sujets/12",
        )

        assert len(posted) == 1
        notified_user, message, url = posted[0]
        assert notified_user is recipient
        assert "Nicolas Mouriou" in message
        assert "L'IA dans la supply chain" in message
        assert url == "https://aipress24.com/wip/sujets/12"
