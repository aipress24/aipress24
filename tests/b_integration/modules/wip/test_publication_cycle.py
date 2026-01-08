# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for Publication Cycle.

These tests cover the integration between different components:
- Article creation (with and without Sujet/Commande/AvisEnquete)
- NotificationPublication after article publication
"""

from __future__ import annotations

from datetime import datetime, timezone

import arrow
from sqlalchemy.orm import scoped_session

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wip.models.newsroom.article import Article, PublicationStatus
from app.modules.wip.models.newsroom.avis_enquete import (
    AvisEnquete,
    ContactAvisEnquete,
    StatutAvis,
)
from app.modules.wip.models.newsroom.notification_publication import (
    NotificationPublication,
    NotificationPublicationContact,
)


# ----------------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------------


def _create_journalist_and_media(
    db_session: scoped_session,
) -> tuple[User, Organisation]:
    """Create a journalist and media organisation."""
    journaliste = User(email="journalist@test.com")
    media = Organisation(name="Test Media")
    db_session.add_all([journaliste, media])
    db_session.flush()
    return journaliste, media


def _create_article(
    db_session: scoped_session,
    owner: User,
    media: Organisation,
    titre: str = "Test Article",
    contenu: str = "Test content for the article.",
) -> Article:
    """Create a publishable article."""
    article = Article(owner=owner, media=media)
    article.titre = titre
    article.contenu = contenu
    article.commanditaire_id = owner.id
    article.date_parution_prevue = arrow.get("2025-03-01").datetime
    db_session.add(article)
    db_session.flush()
    return article


def _create_enquete_with_contacts(
    db_session: scoped_session,
    journaliste: User,
    media: Organisation,
    experts: list[User],
) -> tuple[AvisEnquete, list[ContactAvisEnquete]]:
    """Create an enquête with multiple expert contacts."""
    enquete = AvisEnquete(
        owner=journaliste,
        media=media,
        commanditaire_id=journaliste.id,
        date_debut_enquete=arrow.get("2025-01-01").datetime,
        date_fin_enquete=arrow.get("2025-02-01").datetime,
        date_bouclage=arrow.get("2025-02-15").datetime,
        date_parution_prevue=arrow.get("2025-03-01").datetime,
    )
    db_session.add(enquete)
    db_session.flush()

    contacts = []
    for expert in experts:
        contact = ContactAvisEnquete(
            avis_enquete_id=enquete.id,
            journaliste_id=journaliste.id,
            expert_id=expert.id,
            status=StatutAvis.ACCEPTE,
            date_reponse=datetime.now(timezone.utc),
        )
        db_session.add(contact)
        contacts.append(contact)

    db_session.flush()
    return enquete, contacts


# ----------------------------------------------------------------
# Direct Article Creation Tests
# ----------------------------------------------------------------


class TestDirectArticleCreation:
    """Tests for creating articles directly without the full cycle."""

    def test_article_without_sujet(self, db_session: scoped_session) -> None:
        """Article can be created without a Sujet."""
        journaliste, media = _create_journalist_and_media(db_session)
        article = _create_article(db_session, journaliste, media)

        # Article exists and has no sujet link
        assert article.id is not None
        assert article.owner == journaliste
        assert article.media == media
        # Sujet is not a required field
        assert not hasattr(article, "sujet_id") or article.sujet_id is None

    def test_article_without_commande(self, db_session: scoped_session) -> None:
        """Article can be created without a Commande."""
        journaliste, media = _create_journalist_and_media(db_session)
        article = _create_article(db_session, journaliste, media)

        # Article exists without commande
        assert article.id is not None
        # Commande is not a required field
        assert not hasattr(article, "commande_id") or article.commande_id is None

    def test_article_without_avis_enquete(self, db_session: scoped_session) -> None:
        """Article can be created without an Avis d'Enquête."""
        journaliste, media = _create_journalist_and_media(db_session)
        article = _create_article(db_session, journaliste, media)

        # Article exists without avis enquête
        assert article.id is not None
        # No direct link to avis enquête on article model
        assert not hasattr(article, "avis_enquete_id")

    def test_article_can_be_published_without_cycle(
        self, db_session: scoped_session
    ) -> None:
        """Article can be published without going through full cycle."""
        journaliste, media = _create_journalist_and_media(db_session)
        article = _create_article(db_session, journaliste, media)

        # Initially in draft status
        assert article.status == PublicationStatus.DRAFT

        # Publish the article
        article.publish()

        assert article.status == PublicationStatus.PUBLIC
        # publish() sets published_at
        assert article.published_at is not None


# ----------------------------------------------------------------
# Notification After Publication Tests
# ----------------------------------------------------------------


class TestNotificationAfterPublication:
    """Tests for notification flow after article publication."""

    def test_notification_sent_after_publication(
        self, db_session: scoped_session
    ) -> None:
        """Notification can be created after article is published."""
        journaliste, media = _create_journalist_and_media(db_session)

        # Create experts
        expert1 = User(email="expert1@test.com")
        expert2 = User(email="expert2@test.com")
        db_session.add_all([expert1, expert2])
        db_session.flush()

        # Create enquête with contacts
        enquete, contacts = _create_enquete_with_contacts(
            db_session, journaliste, media, [expert1, expert2]
        )

        # Create and publish article
        article = _create_article(db_session, journaliste, media)
        article.publish()

        # Create notification
        notification = NotificationPublication(
            owner=journaliste,
            avis_enquete=enquete,
            article=article,
        )
        db_session.add(notification)
        db_session.flush()

        # Add contacts to notification
        for contact in contacts:
            notif_contact = NotificationPublicationContact(
                notification=notification,
                contact=contact,
            )
            db_session.add(notif_contact)
        db_session.flush()

        assert notification.id is not None
        assert len(notification.contacts) == 2

    def test_notification_linked_to_correct_article(
        self, db_session: scoped_session
    ) -> None:
        """Notification is linked to the correct article."""
        journaliste, media = _create_journalist_and_media(db_session)
        expert = User(email="expert@test.com")
        db_session.add(expert)
        db_session.flush()

        enquete, contacts = _create_enquete_with_contacts(
            db_session, journaliste, media, [expert]
        )

        # Create and publish article
        article = _create_article(
            db_session, journaliste, media, "My Published Article"
        )
        article.publish()

        # Create notification
        notification = NotificationPublication(
            owner=journaliste,
            avis_enquete=enquete,
            article=article,
        )
        db_session.add(notification)
        db_session.flush()

        assert notification.article_id == article.id
        assert notification.article == article
        assert notification.article.titre == "My Published Article"

    def test_notification_linked_to_correct_avis(
        self, db_session: scoped_session
    ) -> None:
        """Notification is linked to the correct avis d'enquête."""
        journaliste, media = _create_journalist_and_media(db_session)
        expert = User(email="expert@test.com")
        db_session.add(expert)
        db_session.flush()

        enquete, contacts = _create_enquete_with_contacts(
            db_session, journaliste, media, [expert]
        )

        article = _create_article(db_session, journaliste, media)
        article.publish()

        notification = NotificationPublication(
            owner=journaliste,
            avis_enquete=enquete,
            article=article,
        )
        db_session.add(notification)
        db_session.flush()

        assert notification.avis_enquete_id == enquete.id
        assert notification.avis_enquete == enquete


# ----------------------------------------------------------------
# Expert Refusal Scenario Tests
# ----------------------------------------------------------------


class TestExpertRefusalScenario:
    """Tests for scenarios where experts refuse."""

    def test_expert_refuses_then_another_accepts(
        self, db_session: scoped_session
    ) -> None:
        """
        Scenario:
        1. Expert A refuses
        2. Journalist targets Expert B
        3. Expert B accepts
        """
        journaliste, media = _create_journalist_and_media(db_session)

        expert_a = User(email="expert_a@test.com")
        expert_b = User(email="expert_b@test.com")
        db_session.add_all([expert_a, expert_b])
        db_session.flush()

        # Create enquête
        enquete = AvisEnquete(
            owner=journaliste,
            media=media,
            commanditaire_id=journaliste.id,
            date_debut_enquete=arrow.get("2025-01-01").datetime,
            date_fin_enquete=arrow.get("2025-02-01").datetime,
            date_bouclage=arrow.get("2025-02-15").datetime,
            date_parution_prevue=arrow.get("2025-03-01").datetime,
        )
        db_session.add(enquete)
        db_session.flush()

        # Expert A refuses
        contact_a = ContactAvisEnquete(
            avis_enquete_id=enquete.id,
            journaliste_id=journaliste.id,
            expert_id=expert_a.id,
        )
        db_session.add(contact_a)
        db_session.flush()

        contact_a.status = StatutAvis.REFUSE
        contact_a.date_reponse = datetime.now(timezone.utc)

        # Expert B accepts
        contact_b = ContactAvisEnquete(
            avis_enquete_id=enquete.id,
            journaliste_id=journaliste.id,
            expert_id=expert_b.id,
        )
        db_session.add(contact_b)
        db_session.flush()

        contact_b.status = StatutAvis.ACCEPTE
        contact_b.date_reponse = datetime.now(timezone.utc)

        # Verify states
        assert contact_a.status == StatutAvis.REFUSE
        assert contact_a.can_propose_rdv() is False

        assert contact_b.status == StatutAvis.ACCEPTE
        assert contact_b.can_propose_rdv() is True

    def test_all_experts_refuse(self, db_session: scoped_session) -> None:
        """All experts refuse the enquête."""
        journaliste, media = _create_journalist_and_media(db_session)

        expert1 = User(email="expert1@test.com")
        expert2 = User(email="expert2@test.com")
        db_session.add_all([expert1, expert2])
        db_session.flush()

        enquete = AvisEnquete(
            owner=journaliste,
            media=media,
            commanditaire_id=journaliste.id,
            date_debut_enquete=arrow.get("2025-01-01").datetime,
            date_fin_enquete=arrow.get("2025-02-01").datetime,
            date_bouclage=arrow.get("2025-02-15").datetime,
            date_parution_prevue=arrow.get("2025-03-01").datetime,
        )
        db_session.add(enquete)
        db_session.flush()

        contacts = []
        for expert in [expert1, expert2]:
            contact = ContactAvisEnquete(
                avis_enquete_id=enquete.id,
                journaliste_id=journaliste.id,
                expert_id=expert.id,
            )
            db_session.add(contact)
            contacts.append(contact)
        db_session.flush()

        # All experts refuse
        for contact in contacts:
            contact.status = StatutAvis.REFUSE
            contact.date_reponse = datetime.now(timezone.utc)

        # Verify all refused
        for contact in contacts:
            assert contact.status == StatutAvis.REFUSE
            assert contact.can_propose_rdv() is False

        # Journalist can still create article without expert participation
        article = _create_article(db_session, journaliste, media)
        article.publish()
        assert article.status == PublicationStatus.PUBLIC


# ----------------------------------------------------------------
# Multiple Experts Contribute Tests
# ----------------------------------------------------------------


class TestMultipleExpertsContribute:
    """Tests for scenarios with multiple experts."""

    def test_multiple_experts_respond(self, db_session: scoped_session) -> None:
        """Multiple experts respond to the same enquête."""
        journaliste, media = _create_journalist_and_media(db_session)

        experts = []
        for i in range(3):
            expert = User(email=f"expert{i}@test.com")
            db_session.add(expert)
            experts.append(expert)
        db_session.flush()

        enquete, contacts = _create_enquete_with_contacts(
            db_session, journaliste, media, experts
        )

        # All contacts should be in ACCEPTE state
        for contact in contacts:
            assert contact.status == StatutAvis.ACCEPTE

        # Notification can include all contacts
        article = _create_article(db_session, journaliste, media)
        article.publish()

        notification = NotificationPublication(
            owner=journaliste,
            avis_enquete=enquete,
            article=article,
        )
        db_session.add(notification)
        db_session.flush()

        for contact in contacts:
            notif_contact = NotificationPublicationContact(
                notification=notification,
                contact=contact,
            )
            db_session.add(notif_contact)
        db_session.flush()

        assert len(notification.contacts) == 3
