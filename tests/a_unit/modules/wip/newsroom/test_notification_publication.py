# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for NotificationPublication functionality.

NotificationPublication is a WIP module feature that allows journalists
to notify participants of an enquête that the article has been published.

Note: This is NOT the "Justificatif de Publication" which is a commercial
product in the BIZ module.
"""

from __future__ import annotations

from datetime import datetime, timezone

import arrow
from sqlalchemy.orm import scoped_session

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wip.models.newsroom.article import Article
from app.modules.wip.models.newsroom.avis_enquete import (
    AvisEnquete,
    ContactAvisEnquete,
    StatutAvis,
)
from app.modules.wip.models.newsroom.notification_publication import (
    NotificationPublication,
    NotificationPublicationContact,
)


def _create_test_data(
    db_session: scoped_session,
) -> tuple[User, User, Organisation, AvisEnquete, ContactAvisEnquete, Article]:
    """Create a complete set of test data for notification tests."""
    journaliste = User(email="j@test.com")
    expert = User(email="e@test.com")
    media = Organisation(name="Le Journal")
    db_session.add_all([journaliste, expert, media])
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

    contact = ContactAvisEnquete(
        avis_enquete_id=enquete.id,
        journaliste_id=journaliste.id,
        expert_id=expert.id,
        status=StatutAvis.ACCEPTE,
        date_reponse=datetime.now(timezone.utc),
    )
    db_session.add(contact)
    db_session.flush()

    article = Article(owner=journaliste, media=media)
    article.titre = "Test Article"
    article.contenu = "Article body content"
    article.commanditaire_id = journaliste.id
    article.date_parution_prevue = arrow.get("2025-03-01").datetime
    db_session.add(article)
    db_session.flush()

    return journaliste, expert, media, enquete, contact, article


# ----------------------------------------------------------------
# Notification Creation Tests
# ----------------------------------------------------------------


class TestNotificationCreation:
    """Tests for creating a notification."""

    def test_notification_requires_avis_enquete(
        self, db_session: scoped_session
    ) -> None:
        """A notification must be linked to an avis d'enquête."""
        journaliste, expert, media, enquete, contact, article = _create_test_data(
            db_session
        )

        notification = NotificationPublication(
            owner=journaliste,
            avis_enquete=enquete,
            article=article,
        )
        db_session.add(notification)
        db_session.flush()

        assert notification.avis_enquete_id == enquete.id
        assert notification.avis_enquete == enquete

    def test_notification_requires_article(self, db_session: scoped_session) -> None:
        """A notification must be linked to an article."""
        journaliste, expert, media, enquete, contact, article = _create_test_data(
            db_session
        )

        notification = NotificationPublication(
            owner=journaliste,
            avis_enquete=enquete,
            article=article,
        )
        db_session.add(notification)
        db_session.flush()

        assert notification.article_id == article.id
        assert notification.article == article

    def test_notification_sets_notified_at_on_creation(
        self, db_session: scoped_session
    ) -> None:
        """The notification date is set automatically on creation."""
        journaliste, expert, media, enquete, contact, article = _create_test_data(
            db_session
        )

        before = datetime.now(timezone.utc)
        notification = NotificationPublication(
            owner=journaliste,
            avis_enquete=enquete,
            article=article,
        )
        db_session.add(notification)
        db_session.flush()

        assert notification.notified_at is not None
        # notified_at should be around the time of creation
        notified_utc = notification.notified_at.replace(tzinfo=timezone.utc)
        # Allow some tolerance for timezone differences
        assert notified_utc.date() == before.date()

    def test_notification_has_owner(self, db_session: scoped_session) -> None:
        """The notification is linked to the journalist (owner)."""
        journaliste, expert, media, enquete, contact, article = _create_test_data(
            db_session
        )

        notification = NotificationPublication(
            owner=journaliste,
            avis_enquete=enquete,
            article=article,
        )
        db_session.add(notification)
        db_session.flush()

        assert notification.owner_id == journaliste.id
        assert notification.owner == journaliste


# ----------------------------------------------------------------
# Notification Contacts Tests
# ----------------------------------------------------------------


class TestNotificationContacts:
    """Tests for contacts notified."""

    def test_notification_can_have_multiple_contacts(
        self, db_session: scoped_session
    ) -> None:
        """A notification can have multiple contacts."""
        journaliste, expert, media, enquete, contact1, article = _create_test_data(
            db_session
        )

        # Create a second expert and contact
        expert2 = User(email="e2@test.com")
        db_session.add(expert2)
        db_session.flush()

        contact2 = ContactAvisEnquete(
            avis_enquete_id=enquete.id,
            journaliste_id=journaliste.id,
            expert_id=expert2.id,
            status=StatutAvis.ACCEPTE,
            date_reponse=datetime.now(timezone.utc),
        )
        db_session.add(contact2)
        db_session.flush()

        # Create notification with both contacts
        notification = NotificationPublication(
            owner=journaliste,
            avis_enquete=enquete,
            article=article,
        )
        db_session.add(notification)
        db_session.flush()

        # Add contacts to notification
        notif_contact1 = NotificationPublicationContact(
            notification=notification,
            contact=contact1,
        )
        notif_contact2 = NotificationPublicationContact(
            notification=notification,
            contact=contact2,
        )
        db_session.add_all([notif_contact1, notif_contact2])
        db_session.flush()

        assert len(notification.contacts) == 2

    def test_contact_links_to_contact_avis_enquete(
        self, db_session: scoped_session
    ) -> None:
        """Each notification contact is linked to a ContactAvisEnquete."""
        journaliste, expert, media, enquete, contact, article = _create_test_data(
            db_session
        )

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

        assert notif_contact.contact_id == contact.id
        assert notif_contact.contact == contact

    def test_contact_links_back_to_notification(
        self, db_session: scoped_session
    ) -> None:
        """NotificationPublicationContact links back to its notification."""
        journaliste, expert, media, enquete, contact, article = _create_test_data(
            db_session
        )

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

        assert notif_contact.notification_id == notification.id
        assert notif_contact.notification == notification


# ----------------------------------------------------------------
# Cascade Delete Tests
# ----------------------------------------------------------------


class TestCascadeDelete:
    """Tests for cascade deletion behavior."""

    def test_deleting_notification_deletes_contacts(
        self, db_session: scoped_session
    ) -> None:
        """Deleting a notification also deletes its contacts."""
        journaliste, expert, media, enquete, contact, article = _create_test_data(
            db_session
        )

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

        notif_id = notification.id
        notif_contact_id = notif_contact.id

        # Delete the notification
        db_session.delete(notification)
        db_session.flush()

        # Notification and contact should be gone
        assert (
            db_session.query(NotificationPublication).filter_by(id=notif_id).first()
            is None
        )
        assert (
            db_session.query(NotificationPublicationContact)
            .filter_by(id=notif_contact_id)
            .first()
            is None
        )


# ----------------------------------------------------------------
# Fire-and-Forget Model Tests
# ----------------------------------------------------------------


class TestFireAndForgetModel:
    """Tests verifying the simplified fire-and-forget model."""

    def test_notification_has_no_lifecycle_status(
        self, db_session: scoped_session
    ) -> None:
        """NotificationPublication doesn't have lifecycle tracking fields."""
        journaliste, expert, media, enquete, contact, article = _create_test_data(
            db_session
        )

        notification = NotificationPublication(
            owner=journaliste,
            avis_enquete=enquete,
            article=article,
        )
        db_session.add(notification)
        db_session.flush()

        # No lifecycle tracking - just notified_at
        assert hasattr(notification, "notified_at")
        # These should NOT exist
        assert not hasattr(notification, "is_sent")
        assert not hasattr(notification, "sent_at")
        assert not hasattr(notification, "status")

    def test_notification_contact_has_no_tracking_fields(
        self, db_session: scoped_session
    ) -> None:
        """NotificationPublicationContact doesn't have email/in-app tracking."""
        journaliste, expert, media, enquete, contact, article = _create_test_data(
            db_session
        )

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

        # No tracking fields - fire-and-forget
        assert not hasattr(notif_contact, "email_sent")
        assert not hasattr(notif_contact, "email_sent_at")
        assert not hasattr(notif_contact, "inapp_sent")
        assert not hasattr(notif_contact, "inapp_sent_at")


# ----------------------------------------------------------------
# Notification Sending Tests
# ----------------------------------------------------------------


class TestNotificationSendingReadiness:
    """Tests verifying notification data is ready for sending.

    Note: Actual email/in-app sending is fire-and-forget.
    These tests verify the data structure is correct.
    """

    def test_notification_has_all_data_for_email(
        self, db_session: scoped_session
    ) -> None:
        """Notification has all required data for email sending."""
        journaliste, expert, media, enquete, contact, article = _create_test_data(
            db_session
        )

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

        # Verify all data needed for email is accessible
        # 1. Recipient email (via contact -> expert)
        assert notif_contact.contact.expert.email == "e@test.com"

        # 2. Article title
        assert notification.article.titre == "Test Article"

        # 3. Journalist name (sender context)
        assert notification.owner.email == "j@test.com"

        # 4. Media name
        assert notification.article.media.name == "Le Journal"

    def test_notification_contacts_have_expert_access(
        self, db_session: scoped_session
    ) -> None:
        """Each notification contact provides access to expert user."""
        journaliste, expert, media, enquete, contact, article = _create_test_data(
            db_session
        )

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

        # Navigate to expert through contact
        expert_user = notif_contact.contact.expert
        assert expert_user is not None
        assert expert_user.email is not None

    def test_all_accepted_contacts_can_be_notified(
        self, db_session: scoped_session
    ) -> None:
        """Only contacts with ACCEPTE status should be notified."""
        from app.modules.wip.models.newsroom.avis_enquete import StatutAvis

        journaliste, expert1, media, enquete, contact1, article = _create_test_data(
            db_session
        )

        # Create second expert who refused
        expert2 = User(email="e2@test.com")
        db_session.add(expert2)
        db_session.flush()

        contact2 = ContactAvisEnquete(
            avis_enquete_id=enquete.id,
            journaliste_id=journaliste.id,
            expert_id=expert2.id,
            status=StatutAvis.REFUSE,
            date_reponse=datetime.now(timezone.utc),
        )
        db_session.add(contact2)
        db_session.flush()

        # Create notification
        notification = NotificationPublication(
            owner=journaliste,
            avis_enquete=enquete,
            article=article,
        )
        db_session.add(notification)
        db_session.flush()

        # Only add accepted contacts to notification
        accepted_contacts = [contact1]  # contact2 refused
        for contact in accepted_contacts:
            if contact.status == StatutAvis.ACCEPTE:
                notif_contact = NotificationPublicationContact(
                    notification=notification,
                    contact=contact,
                )
                db_session.add(notif_contact)
        db_session.flush()

        # Only 1 contact (the accepted one) should be in notification
        assert len(notification.contacts) == 1
        assert notification.contacts[0].contact.status == StatutAvis.ACCEPTE

    def test_notification_ready_for_inapp_notification(
        self, db_session: scoped_session
    ) -> None:
        """Notification data is ready for in-app notification creation."""
        journaliste, expert, media, enquete, contact, article = _create_test_data(
            db_session
        )

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

        # Data needed for in-app notification:
        # 1. Receiver (expert user)
        receiver = notif_contact.contact.expert
        assert receiver.id is not None

        # 2. Message content (can be built from article title)
        article_title = notification.article.titre
        assert article_title

        # 3. URL (can be built from article id)
        article_id = notification.article.id
        assert article_id is not None
