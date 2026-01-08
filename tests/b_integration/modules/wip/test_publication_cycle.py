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
    RDVStatus,
    RDVType,
    StatutAvis,
)
from app.modules.wip.models.newsroom.commande import Commande
from app.modules.wip.models.newsroom.notification_publication import (
    NotificationPublication,
    NotificationPublicationContact,
)
from app.modules.wip.models.newsroom.sujet import Sujet


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


# ----------------------------------------------------------------
# Avis Enquête to Article Flow Tests
# ----------------------------------------------------------------


class TestAvisEnqueteToArticleFlow:
    """Tests for the flow from Avis d'Enquête to Article."""

    def test_article_created_after_rdv_accepted(
        self, db_session: scoped_session
    ) -> None:
        """Article can be created after RDV is accepted."""
        from datetime import timedelta

        from app.modules.wip.models.newsroom.avis_enquete import RDVStatus, RDVType

        journaliste, media = _create_journalist_and_media(db_session)
        expert = User(email="expert@test.com")
        db_session.add(expert)
        db_session.flush()

        enquete, contacts = _create_enquete_with_contacts(
            db_session, journaliste, media, [expert]
        )
        contact = contacts[0]

        # Expert has accepted, now propose RDV
        assert contact.can_propose_rdv() is True

        # Generate valid future slots (weekday, business hours)
        now = datetime.now(timezone.utc)
        days_ahead = 1
        while (now + timedelta(days=days_ahead)).weekday() >= 5:  # Skip weekend
            days_ahead += 1
        slot1 = (now + timedelta(days=days_ahead)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )

        # Propose RDV
        contact.propose_rdv(
            rdv_type=RDVType.PHONE,
            proposed_slots=[slot1],
            rdv_phone="0123456789",
        )
        assert contact.rdv_status == RDVStatus.PROPOSED

        # Expert accepts the RDV
        contact.accept_rdv(selected_slot=slot1, expert_notes="Looking forward to it")
        assert contact.rdv_status == RDVStatus.ACCEPTED
        assert contact.date_rdv == slot1

        # After RDV, journalist creates article
        article = _create_article(
            db_session,
            journaliste,
            media,
            titre="Article based on expert interview",
            contenu="Content from the interview with expert.",
        )
        article.publish()

        assert article.status == PublicationStatus.PUBLIC

        # Notification can be sent
        notification = NotificationPublication(
            owner=journaliste,
            avis_enquete=enquete,
            article=article,
        )
        db_session.add(notification)
        db_session.flush()

        notif_contact = NotificationPublicationContact(
            notification=notification,
            contact=contact,
        )
        db_session.add(notif_contact)
        db_session.flush()

        assert notification.id is not None
        assert len(notification.contacts) == 1

    def test_article_can_be_created_before_rdv(
        self, db_session: scoped_session
    ) -> None:
        """Article can be created even before RDV (direct creation path)."""
        journaliste, media = _create_journalist_and_media(db_session)
        expert = User(email="expert@test.com")
        db_session.add(expert)
        db_session.flush()

        enquete, contacts = _create_enquete_with_contacts(
            db_session, journaliste, media, [expert]
        )
        contact = contacts[0]

        # Expert accepted but no RDV yet
        assert contact.status == StatutAvis.ACCEPTE
        assert contact.can_propose_rdv() is True  # RDV not yet proposed

        # Journalist can still create article (maybe from other sources)
        article = _create_article(db_session, journaliste, media)
        article.publish()

        assert article.status == PublicationStatus.PUBLIC


# ----------------------------------------------------------------
# Expert Invitation Flow Tests
# ----------------------------------------------------------------


class TestExpertInvitationFlow:
    """Tests for expert invitation workflow.

    Note: These tests verify the data flow. Actual notification/email
    sending is tested separately with service mocks.
    """

    def test_invitation_creates_contact_in_pending_state(
        self, db_session: scoped_session
    ) -> None:
        """When expert is invited, a contact is created in EN_ATTENTE state."""
        journaliste, media = _create_journalist_and_media(db_session)
        expert = User(email="expert@test.com")
        db_session.add(expert)
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

        # Create invitation (contact)
        contact = ContactAvisEnquete(
            avis_enquete_id=enquete.id,
            journaliste_id=journaliste.id,
            expert_id=expert.id,
        )
        db_session.add(contact)
        db_session.flush()

        # Contact should be in pending state
        assert contact.status == StatutAvis.EN_ATTENTE
        assert contact.date_reponse is None
        assert contact.can_propose_rdv() is False

    def test_rdv_acceptance_updates_contact_state(
        self, db_session: scoped_session
    ) -> None:
        """When expert accepts RDV, contact state is updated."""
        from datetime import timedelta

        from app.modules.wip.models.newsroom.avis_enquete import RDVStatus, RDVType

        journaliste, media = _create_journalist_and_media(db_session)
        expert = User(email="expert@test.com")
        db_session.add(expert)
        db_session.flush()

        enquete, contacts = _create_enquete_with_contacts(
            db_session, journaliste, media, [expert]
        )
        contact = contacts[0]

        # Generate valid slot
        now = datetime.now(timezone.utc)
        days_ahead = 1
        while (now + timedelta(days=days_ahead)).weekday() >= 5:
            days_ahead += 1
        slot = (now + timedelta(days=days_ahead)).replace(
            hour=14, minute=0, second=0, microsecond=0
        )

        # Propose and accept RDV
        contact.propose_rdv(
            rdv_type=RDVType.VIDEO,
            proposed_slots=[slot],
            rdv_video_link="https://meet.example.com/abc",
        )
        contact.accept_rdv(selected_slot=slot)

        # Verify state
        assert contact.rdv_status == RDVStatus.ACCEPTED
        assert contact.date_rdv == slot
        assert contact.rdv_type == RDVType.VIDEO

    def test_multiple_invitations_independent(self, db_session: scoped_session) -> None:
        """Multiple expert invitations are independent of each other."""
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

        # Create two independent contacts
        contact1 = ContactAvisEnquete(
            avis_enquete_id=enquete.id,
            journaliste_id=journaliste.id,
            expert_id=expert1.id,
        )
        contact2 = ContactAvisEnquete(
            avis_enquete_id=enquete.id,
            journaliste_id=journaliste.id,
            expert_id=expert2.id,
        )
        db_session.add_all([contact1, contact2])
        db_session.flush()

        # Expert 1 accepts
        contact1.status = StatutAvis.ACCEPTE
        contact1.date_reponse = datetime.now(timezone.utc)

        # Expert 2 refuses
        contact2.status = StatutAvis.REFUSE
        contact2.date_reponse = datetime.now(timezone.utc)

        # States are independent
        assert contact1.status == StatutAvis.ACCEPTE
        assert contact2.status == StatutAvis.REFUSE
        assert contact1.can_propose_rdv() is True
        assert contact2.can_propose_rdv() is False


# ----------------------------------------------------------------
# Full Publication Cycle Tests
# ----------------------------------------------------------------


class TestFullPublicationCycle:
    """Tests for the complete publication cycle from Sujet to Notification.

    This tests the full workflow:
    1. Journalist creates Sujet
    2. Sujet validated (status change)
    3. Commande created from Sujet
    4. AvisEnquete created
    5. Expert targeting and invitation
    6. Expert accepts
    7. RDV proposed and accepted
    8. Article created and published
    9. Notification de publication sent
    """

    def test_full_cycle_sujet_to_notification(self, db_session: scoped_session) -> None:
        """Complete publication cycle from Sujet to Notification."""
        from datetime import timedelta

        # Step 1: Create journalist, media, and expert
        journaliste = User(email="journalist@test.com")
        media = Organisation(name="Le Journal")
        expert = User(email="expert@test.com")
        db_session.add_all([journaliste, media, expert])
        db_session.flush()

        # Step 2: Journalist creates Sujet
        sujet = Sujet(
            owner=journaliste,
            media=media,
            commanditaire_id=journaliste.id,
            titre="Investigation sur le climat",
            brief="Enquête sur les nouvelles réglementations climat",
            date_limite_validite=arrow.get("2025-01-15").datetime,
            date_parution_prevue=arrow.get("2025-03-01").datetime,
        )
        db_session.add(sujet)
        db_session.flush()

        assert sujet.id is not None
        assert sujet.titre == "Investigation sur le climat"
        assert sujet.status == PublicationStatus.DRAFT  # default

        # Step 3: Sujet validated
        sujet.status = PublicationStatus.PENDING  # type: ignore[assignment]

        # Step 4: Commande created
        commande = Commande(
            owner=journaliste,
            media=media,
            commanditaire_id=journaliste.id,
            titre=sujet.titre,
            brief=sujet.brief,
            date_limite_validite=arrow.get("2025-02-01").datetime,
            date_bouclage=arrow.get("2025-02-15").datetime,
            date_parution_prevue=arrow.get("2025-03-01").datetime,
            date_paiement=arrow.get("2025-04-01").datetime,
        )
        db_session.add(commande)
        db_session.flush()

        assert commande.id is not None
        assert commande.status == PublicationStatus.DRAFT  # default

        # Step 5: AvisEnquete created
        enquete = AvisEnquete(
            owner=journaliste,
            media=media,
            commanditaire_id=journaliste.id,
            date_debut_enquete=arrow.get("2025-01-10").datetime,
            date_fin_enquete=arrow.get("2025-02-01").datetime,
            date_bouclage=arrow.get("2025-02-15").datetime,
            date_parution_prevue=arrow.get("2025-03-01").datetime,
        )
        db_session.add(enquete)
        db_session.flush()

        # Step 6: Expert targeting - create contact
        contact = ContactAvisEnquete(
            avis_enquete_id=enquete.id,
            journaliste_id=journaliste.id,
            expert_id=expert.id,
        )
        db_session.add(contact)
        db_session.flush()

        # Initially pending
        assert contact.status == StatutAvis.EN_ATTENTE
        assert contact.can_propose_rdv() is False

        # Step 7: Expert accepts
        contact.status = StatutAvis.ACCEPTE
        contact.date_reponse = datetime.now(timezone.utc)

        assert contact.can_propose_rdv() is True

        # Step 8: RDV proposed
        now = datetime.now(timezone.utc)
        days_ahead = 1
        while (now + timedelta(days=days_ahead)).weekday() >= 5:
            days_ahead += 1
        slot = (now + timedelta(days=days_ahead)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )

        contact.propose_rdv(
            rdv_type=RDVType.VIDEO,
            proposed_slots=[slot],
            rdv_video_link="https://meet.example.com/interview",
        )

        assert contact.rdv_status == RDVStatus.PROPOSED

        # Step 9: Expert accepts RDV
        contact.accept_rdv(selected_slot=slot, expert_notes="Confirmed")

        assert contact.rdv_status == RDVStatus.ACCEPTED
        assert contact.date_rdv == slot

        # Step 10: Article created
        article = Article(owner=journaliste, media=media)
        article.titre = "Le climat en 2025: nouvelles réglementations"
        article.contenu = "Contenu de l'article basé sur les interviews..."
        article.commanditaire_id = journaliste.id
        article.date_parution_prevue = arrow.get("2025-03-01").datetime
        db_session.add(article)
        db_session.flush()

        # Step 11: Article published
        article.publish()

        assert article.status == PublicationStatus.PUBLIC
        assert article.published_at is not None

        # Step 12: Notification sent
        notification = NotificationPublication(
            owner=journaliste,
            avis_enquete=enquete,
            article=article,
        )
        db_session.add(notification)
        db_session.flush()

        notif_contact = NotificationPublicationContact(
            notification=notification,
            contact=contact,
        )
        db_session.add(notif_contact)
        db_session.flush()

        # Verify final state
        assert notification.id is not None
        assert notification.notified_at is not None
        assert notification.article == article
        assert notification.avis_enquete == enquete
        assert len(notification.contacts) == 1
        assert notification.contacts[0].contact.expert == expert

    def test_cycle_with_multiple_experts(self, db_session: scoped_session) -> None:
        """Full cycle with multiple experts participating."""
        from datetime import timedelta

        # Setup
        journaliste = User(email="journalist@test.com")
        media = Organisation(name="Media Corp")
        expert1 = User(email="expert1@test.com")
        expert2 = User(email="expert2@test.com")
        expert3 = User(email="expert3@test.com")
        db_session.add_all([journaliste, media, expert1, expert2, expert3])
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

        # Create contacts for all experts
        contacts = []
        for expert in [expert1, expert2, expert3]:
            contact = ContactAvisEnquete(
                avis_enquete_id=enquete.id,
                journaliste_id=journaliste.id,
                expert_id=expert.id,
            )
            db_session.add(contact)
            contacts.append(contact)
        db_session.flush()

        # Expert 1 accepts
        contacts[0].status = StatutAvis.ACCEPTE
        contacts[0].date_reponse = datetime.now(timezone.utc)

        # Expert 2 refuses
        contacts[1].status = StatutAvis.REFUSE
        contacts[1].date_reponse = datetime.now(timezone.utc)

        # Expert 3 accepts
        contacts[2].status = StatutAvis.ACCEPTE
        contacts[2].date_reponse = datetime.now(timezone.utc)

        # RDV with Expert 1
        now = datetime.now(timezone.utc)
        days_ahead = 1
        while (now + timedelta(days=days_ahead)).weekday() >= 5:
            days_ahead += 1
        slot = (now + timedelta(days=days_ahead)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )

        contacts[0].propose_rdv(
            rdv_type=RDVType.PHONE,
            proposed_slots=[slot],
            rdv_phone="0123456789",
        )
        contacts[0].accept_rdv(selected_slot=slot)

        # RDV with Expert 3
        slot2 = (now + timedelta(days=days_ahead + 1)).replace(
            hour=14, minute=0, second=0, microsecond=0
        )
        # Skip weekend for second slot
        while slot2.weekday() >= 5:
            slot2 += timedelta(days=1)

        contacts[2].propose_rdv(
            rdv_type=RDVType.VIDEO,
            proposed_slots=[slot2],
            rdv_video_link="https://meet.example.com/call",
        )
        contacts[2].accept_rdv(selected_slot=slot2)

        # Publish article
        article = Article(owner=journaliste, media=media)
        article.titre = "Multi-expert investigation"
        article.contenu = "Content from multiple expert interviews"
        article.commanditaire_id = journaliste.id
        article.date_parution_prevue = arrow.get("2025-03-01").datetime
        db_session.add(article)
        db_session.flush()
        article.publish()

        # Send notification to accepted experts only
        notification = NotificationPublication(
            owner=journaliste,
            avis_enquete=enquete,
            article=article,
        )
        db_session.add(notification)
        db_session.flush()

        # Only notify experts who accepted
        accepted_contacts = [c for c in contacts if c.status == StatutAvis.ACCEPTE]
        for contact in accepted_contacts:
            notif_contact = NotificationPublicationContact(
                notification=notification,
                contact=contact,
            )
            db_session.add(notif_contact)
        db_session.flush()

        # Verify: 2 contacts notified (expert1 and expert3)
        assert len(notification.contacts) == 2
        notified_experts = [nc.contact.expert for nc in notification.contacts]
        assert expert1 in notified_experts
        assert expert2 not in notified_experts  # refused
        assert expert3 in notified_experts

    def test_cycle_article_without_rdv_completion(
        self, db_session: scoped_session
    ) -> None:
        """Article can be published even if some RDVs are not completed."""
        journaliste = User(email="journalist@test.com")
        media = Organisation(name="Fast News")
        expert = User(email="expert@test.com")
        db_session.add_all([journaliste, media, expert])
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

        # Create contact - expert accepts but RDV only proposed (not accepted yet)
        contact = ContactAvisEnquete(
            avis_enquete_id=enquete.id,
            journaliste_id=journaliste.id,
            expert_id=expert.id,
            status=StatutAvis.ACCEPTE,
            date_reponse=datetime.now(timezone.utc),
            rdv_status=RDVStatus.PROPOSED,  # RDV proposed but not accepted
        )
        db_session.add(contact)
        db_session.flush()

        # Journalist can still publish article (maybe deadline pressure)
        article = Article(owner=journaliste, media=media)
        article.titre = "Breaking news article"
        article.contenu = "Published without expert RDV"
        article.commanditaire_id = journaliste.id
        article.date_parution_prevue = arrow.get("2025-03-01").datetime
        db_session.add(article)
        db_session.flush()

        # Can publish without RDV completion
        article.publish()
        assert article.status == PublicationStatus.PUBLIC

        # Can still send notification (to inform experts that article is out)
        notification = NotificationPublication(
            owner=journaliste,
            avis_enquete=enquete,
            article=article,
        )
        db_session.add(notification)
        db_session.flush()

        notif_contact = NotificationPublicationContact(
            notification=notification,
            contact=contact,
        )
        db_session.add(notif_contact)
        db_session.flush()

        assert notification.id is not None
